# ADR 0004: LangGraph Checkpoint - 站在 PostgresSaver 肩上

- 状态: Accepted
- 日期: 2026-08-07
- 关联: 设计文档 3.4 模块三 / 开发计划 P8 关键决策 / ADR 0003

## Context

P8(M7) 需要为 Multi-Agent 编排提供 checkpoint 能力: 状态序列化、断点续跑、
父子 checkpoint 链路(lineage)追踪。设计文档 3.4 模块三给出 CheckpointManager
四件套(save/restore/lineage), 并要求 "站在 LangGraph 肩上而非重复造轮子"。

LangGraph 生态提供 `langgraph-checkpoint-postgres` 包(PostgresSaver /
AsyncPostgresSaver), 原生实现 checkpoint 写入、读取、时间旅行与断点续跑,
并**原生维护 `parent_checkpoint_id` 字段**(每个新 checkpoint 自动记录其父节点)。

冲突点: AsyncPostgresSaver 固定使用 `checkpoints` / `checkpoint_blobs` /
`checkpoint_writes` 三张表(结构: thread_id / checkpoint_ns / checkpoint_id /
parent_checkpoint_id / checkpoint / metadata), 与 P2 阶段按设计文档建的 ORM
`checkpoints` 表(id / agent_run_id / parent_checkpoint_id / state / created_at)
**同名且结构不兼容**, 无法并存。

## Decision

**完全采用 LangGraph 原生表**, 不保留自研 checkpoint 表:

- 删除 ORM `Checkpoint` 模型与 `CheckpointRepo`, 新增迁移 0002 删除旧
  `checkpoints` 表。LangGraph 侧表由 `saver.setup()` 自动创建, 不入 alembic 管理。
- `agents/checkpoint.py` 提供 `CheckpointManager` 门面, 封装 AsyncPostgresSaver:
  - `save(state, thread_id, parent_checkpoint_id, metadata)` → 返回 LangGraph
    生成的 checkpoint_id
  - `restore(thread_id, checkpoint_id=None)` → 反序列化恢复 AgentState
  - `lineage(thread_id, checkpoint_id)` → 沿原生 `parent_checkpoint_id` 向上
    回溯, 返回完整链路(用于 replay 演示)
- `thread_id` 用 `str(agent_run_id)`, 一个 Agent run 一条线程, 线程内每次节点
  边界自动写 checkpoint 并形成父子链; `TaskDelegation.checkpoint_id` 字段存
  LangGraph checkpoint_id(该表是业务映射, 与 checkpoint 数据解耦)。
- 断点续跑: 同一 `thread_id` + 指定 `checkpoint_id` 调 `invoke`, LangGraph
  从该 checkpoint 恢复 channel 状态继续执行。

## Consequences

正面:
- 站在 LangGraph 肩上: 序列化协议(channel versions / checkpoint_blobs /
  checkpoint_writes)、时间旅行、并发写入冲突处理全部复用官方实现, 不自研。
- parent_checkpoint_id 原生维护, lineage 与断点续跑开箱即用。
- 面试叙事清晰: "为什么不用自研表" → 官方 saver 已解决同一问题, 我们只做门面。

负面:
- 引入 psycopg v3 依赖(AsyncPostgresSaver 的固有依赖), 与项目 async 栈
  (asyncpg)并存; 二者均为 PostgreSQL 驱动, 无冲突。
- 旧 checkpoints 表数据(如有)随迁移 0002 删除; P2-P7 期间该表仅占位,
  无实际数据, 无迁移成本。
- checkpoint 业务归属(agent_run_id)需靠 thread_id 约定, 无外键约束,
  由 CheckpointManager 封装保证一致性。

## 备选方案

- 保留自研表 + 自研 BaseCheckpointSaver: 需实现 channel 版本/writes 协议,
  违背 "站在 LangGraph 肩上" 的既定决策, 风险高, 已否决。
- 双表并存(业务映射表 + LangGraph 独立 schema): 复杂度高、连接需带
  search_path、state 重复存储, 已否决。
