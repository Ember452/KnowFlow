# M7 · Multi-Agent 编排 — 指标/验收测试文档

> 按 AGENTS.md 2.2 节要求编写。编排核心逻辑(状态机路由/委派协议/并发执行/checkpoint
> 序列化与 lineage/子 Agent 工具化)已在 `tests/unit/agents` 自动验证(51 个用例, 全部离线可测);
> 并发较串行耗时下降已由 `scripts/benchmark_multiagent.py` 静态模式自动实测
> (docs/benchmarks/multiagent_20260807.md, 均值 65.8% 达标);
> 真实 LLM 委派链路、断点续跑、子 Agent 真实工具调用三项验收需真实服务, 交由用户实测后回填。

---

## 一、前置条件

### 1.1 依赖服务

```bash
docker compose up -d
docker compose ps          # postgres / milvus / redis / minio 均 healthy
```

### 1.2 环境变量

`.env` 已填入真实值:

- `KNOWFLOW_LLM_API_KEY` / `KNOWFLOW_LLM_BASE_URL` / `KNOWFLOW_LLM_MODEL`(DeepSeek 等,
  规划/子 Agent/汇总均用同一模型)
- 编排参数(默认即可): `KNOWFLOW_AGENT_TIMEOUT_SECONDS=60`(子 Agent 超时)/
  `KNOWFLOW_AGENT_MAX_SUBTASKS=5`(最大委派子任务数)

### 1.3 初始化与门禁

```bash
uv run python scripts/init_db.py          # 建库 + 迁移(0002 已删除旧 checkpoints 表)
uv run ruff check src/ tests/ scripts/ worker/    # 0 errors
uv run mypy src/ worker/                  # 0 errors
uv run pytest tests/unit -q               # 全绿
uv run pytest tests/unit/agents -q        # M7 专项 51 用例(含子 Agent 工具化)
uv run python scripts/benchmark_multiagent.py     # 并发较串行下降 >= 60%
```

> 注: 0002 迁移会删除 P2 遗留的 checkpoints 表; LangGraph checkpoint 三表
> (checkpoints/checkpoint_blobs/checkpoint_writes)由 saver.setup() 自动创建,
> 首次触发编排时建表(见 docs/adr/0004-langgraph-checkpoint.md)。

---

## 二、启动步骤

```bash
# 终端 1: API(需先启动 docker compose 四件套)
uv run uvicorn knowflow.main:app --reload --port 8000

# 确认服务就绪
curl http://localhost:8000/api/v1/readyz     # 期望 deps 全 ok
```

> 编排链路随 chat 端点启用(依赖齐备时自动装配): 复杂任务(规则判 complex,
> 如含"对比/分别/汇总"等信号词)走 LangGraph 状态机 → 主 Agent LLM 规划 →
> 并发委派子 Agent → 汇总; 简单问答直连检索链路, 不受影响。
> 子 Agent 工具化: 注入 ToolOrchestrator 后, 子 Agent 以 SUBAGENT 角色跑工具循环,
> 可见 subagent_only 域工具(code_review / report_writing 技能, 主 Agent 不可见);
> 依赖 skills/ 目录 5 个 Skill 正常加载(SkillManager 自动装配)。

---

## 三、测试用例与结果记录

### 用例 1: 复杂任务触发委派(核心验收)

```bash
curl.exe -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" `
  -d '{"user_id":"demo","message":"对比 A/B/C 三款产品的价格与参数并汇总"}'
```

- **预期**: 响应 answer 为汇总结果(三款产品对比); 数据库 agent_runs 表出现
  1 条 main + 2-3 条 sub(parent_run_id 指向 main), task_delegations 对应记录
  status=completed。

### 用例 2: 状态机可见性(父子 run 与委派链)

```bash
# run_id 取用例 1 的 main run id
curl.exe -s http://localhost:8000/api/v1/agents/runs/1
```

- **预期**: `run.agent_type="main"`; `children` 数组含全部 sub run(agent_type=sub,
  status=completed); `delegations` 数组含对应委派记录(task/status/checkpoint_id)。

### 用例 3: 简单问答直连(不误伤)

```bash
curl.exe -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" `
  -d '{"user_id":"demo","message":"公司报销流程是什么?"}'
```

- **预期**: 正常回答; agent_runs 表不新增记录(未走编排, 直连检索链路)。

### 用例 4: 子任务失败降级

- 场景: 知识库缺少某产品资料时, 该子任务输出"(知识库中未找到相关信息)"或失败。
- **预期**: 其他子任务正常完成, 汇总答案注明"该部分未能获取"; 主 run 仍 completed,
  失败子任务 delegation status=failed。

### 用例 5: 断点续跑(核心验收)

按 `docs/demo_checkpoint.md` 步骤 4 执行:

```bash
uv run python -c "
import asyncio
from knowflow.agents.checkpoint import CheckpointManager

async def main():
    mgr = CheckpointManager()
    state = await mgr.restore('1')          # run_id 替换为用例 1 的 main run id
    print(state.get('query'), state.get('needs_delegation'))
    chain = await mgr.lineage('1')
    print('checkpoint 链深度:', len(chain))

asyncio.run(main())
"
```

- **预期**: 恢复状态含 query/needs_delegation/subtask_results; lineage 链深度 >= 3,
  每项含 parent_checkpoint_id(父子链)。

### 用例 6: 并发较串行耗时下降(自动验证)

```bash
uv run python scripts/benchmark_multiagent.py --report
```

- **预期**: 均值 >= 60%(目标 77.6%); 报告写入 docs/benchmarks/multiagent_2026xxxx.md。
- 真实模式(可选, LLM + PG 齐备时): `uv run python scripts/benchmark_multiagent.py --mode real`。

### 用例 7: 子 Agent 工具调用(核心验收, 流式)

```bash
curl.exe -s -N -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" `
  -d '{"user_id":"demo","message":"对比 A/B 产品的价格参数, 并撰写一份简短对比报告"}'
```

- **预期**: SSE 事件流出现 `tool_start` / `tool_end` 事件且带 `subtask_id` 字段
  (标注工具调用来自哪个子 Agent); 数据库 task_delegations 结果含工具调用记录;
  子 Agent 可调用 subagent_only 域工具(如 report_writing 技能链: 检索 + 计算 + 文件写出),
  主 Agent 对话中看不到这些工具(可在 /api/v1/skills 验证 report_writing/code_review 仅子 Agent 可见)。
- 验证 Skill 数量: `GET /api/v1/skills` 返回 5 个(report_writing 为新增)。

---

## 四、结果记录表(待用户实测回填)

| 用例 | 结果(通过/失败) | 实测数据/截图 | 备注 |
|---|---|---|---|
| 1 复杂任务委派 | | | |
| 2 状态机可见性 | | | |
| 3 简单问答直连 | | | |
| 4 失败降级 | | | |
| 5 断点续跑 | | | |
| 6 并发耗时下降 | | 静态模式已自动记录 | docs/benchmarks/multiagent_20260807.md |
| 7 子 Agent 工具调用 | | | 需真实 LLM + 工具服务 |

> 用户按本文档实测后, 将结果表/截图反馈给 AI; AI 将实测数据写入
> docs/benchmarks/multiagent_2026xxxx.md 并保留本文档作为证据。
