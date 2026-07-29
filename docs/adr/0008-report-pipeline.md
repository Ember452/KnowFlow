# ADR 0008: 报告生成链路用独立流水线模块

- 状态: Accepted
- 日期: 2026-08-10
- 关联: 设计文档 5.2 / 5.7 D8 / P12 研究报告生成流水线

## Context

V2 改造引入"研究报告生成"场景：用户需求 → 多 Agent 并行调研（知识库/记忆/联网）→
融合 → 分章节撰写 → 事实核查 → 发布。既有 MultiAgentOrchestrator 面向问答场景，
产出物是单一答案，状态机为 understand → plan → execute → summarize。

两个场景的产出物与阶段完全不同：

- 问答：单答案、无引用规范、最多一轮委派；
- 报告：结构化章节 + 证据包 + 参考文献表，强制 `[n]` 引用标注，含调研/融合/审查/发布阶段。

若在现有 orchestrator 中扩展报告分支，状态机将同时承担两种产出物，规划/汇总逻辑互相污染，
且报告专属阶段（Synthesizer/Reviewer/Publisher）无自然挂载点。

## Decision

**新增独立模块 `agents/report/`（ReportPipeline 六阶段流水线）**，与问答编排器并存：
规划 → 并行调研 → 融合 → 撰写 → 审查 → 发布。复用既有基础设施：Subagent（独立上下文）、
concurrent（asyncio.gather 并发）、checkpoint（断点续跑）、retrieval（混合检索）、
memory（长期记忆召回）、tools（执行域隔离）。问答链路零改动。

## Consequences

正面:
- 职责清晰: 两条链路各自演进, 报告可独立评测(引用覆盖率/幻觉率).
- 问答链路零风险: 不触碰已验收的 orchestrator 代码.
- 复用而非重复: 编排/并发/检索/记忆全部复用, 新增代码集中在报告专属阶段.

负面:
- 两条链路并存, 需维护两套入口(chat_service vs report_service).
- 报告链路初期无独立评测集, M1 阶段需新建报告评测集.
