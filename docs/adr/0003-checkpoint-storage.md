# ADR 0003: Checkpoint 存储位置 - PostgreSQL 而非 Redis

- 状态: Accepted
- 日期: 2026-08-05
- 关联: 设计文档 3.2 架构图 / 3.4 模块三 / 开发计划 P2 关键决策

## Context

设计文档 3.2 系统架构图中, 存储层标注 "Redis(会话+记忆+checkpoint)", 暗示 checkpoint 存 Redis.
但 checkpoint 是 Multi-Agent 断点续跑的核心状态(序列化的 AgentState), 丢失会导致任务无法恢复;
Redis 作为内存数据库, 重启或故障时数据可能丢失(RDB/AOF 持久化有窗口).

同时, P8 计划采用 LangGraph 原生 `PostgresSaver` 作为 checkpoint saver(见 ADR 0004),
若 checkpoint 存 Redis 则需自研 Redis 版 saver, 与"站在 LangGraph 肩上"的取舍相悖.

## Decision

**checkpoints 表建在 PostgreSQL**, 与设计文档 3.4 模块三的表设计一致.
Redis 仅承担会话级热缓存职责: 短期记忆 / 限流 / 任务队列 / SSE 心跳, 不存 checkpoint 本体.

## Consequences

正面:
- 持久化保证: PG 持久化, Redis 宕机不丢 checkpoint, 断点续跑可靠.
- 与 LangGraph PostgresSaver 对齐: P8 直接复用, 不自研 saver.
- lineage 查询: 父子 checkpoint 链路用 SQL 递归 CTE 实现, 无需额外组件.
- 与业务数据同库: agent_runs / task_delegations / checkpoints 同在 PG, 事务一致.

负面:
- 写入延迟略高于纯 Redis(网络+磁盘), 但 checkpoint 写入不频繁(每个节点边界一次), 可接受.
- Redis 不再承担 checkpoint 职责, 架构图 3.2 的 "checkpoint" 标注需以本 ADR 为准.

## 与架构图 3.2 的差异说明

架构图 3.2 标注 Redis 存储 checkpoint, 本 ADR 将其改为 PostgreSQL.
这是 P2 阶段对架构图细节的修正, 不修改设计文档原文, 以本 ADR 为最终决策.
