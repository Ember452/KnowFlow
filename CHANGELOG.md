# Changelog

本文件记录 KnowFlow 项目的所有显著变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 项目脚手架与工程规范（P0）：pyproject.toml、目录骨架、docker-compose、pre-commit、Makefile
- 核心基础设施（P1）：配置/常量/异常/日志/生命周期/连接池
- ORM 模型与 Repository（P2）：9 个模型文件、Alembic 迁移、5 个 Repository
- GraphRAG 检索（P3）：解析/分块/实体抽取/混合检索(RRF)/一跳扩展/精排/缓存/索引管线
- API 层与异步索引（P4）：8 个 Schema、9 组端点、文档服务、Redis Stream 任务队列与 Worker
- 对话链路与 SSE 流式（P5）：检索增强问答、检索/Token/工具/Done 事件流、心跳与断开检测
- 工具治理与 Skill 体系（P6）：执行域隔离、可见性计算、权限拦截、4 个内置工具、4 个 Skill、指标脚本
- 沙盒文件系统（P9）：虚拟路径映射、访问控制、配额、MinIO 后端、file_tools 真实接入
- 上下文工程（P7）：token 计数/预算分配/滑动窗口/历史摘要/超阈值卸载/策略编排
- 记忆体系（P7）：Redis 短期记忆、重要性打分、LLM 压缩、PG 长期存储与向量召回、沉淀编排
- Multi-Agent 编排（P8）：LangGraph 状态机（understand/plan/execute/summarize 条件路由）、
  主/子 Agent、TaskDelegation 委派协议、asyncio.gather 并发执行（超时/降级）、
  CheckpointManager 封装 AsyncPostgresSaver（save/restore/lineage 断点续跑）

### Changed
- 对话链路接入工具编排（M5 完善）：预检索上下文注入 ToolOrchestrator，工具调用记录随响应返回并落库
- benchmark_tools.py 新增真实模式（--mode real）：真实 LLM 跑工具调用循环统计 FC 准确率
- 对话链路接入记忆与上下文策略（M6）：召回注入系统提示、消息观察短期、每 5 轮自动沉淀、预算/窗口/摘要/卸载生效
- memory 端点接入实现（M6）：查询/删除/手动沉淀
- 对话链路接入多 Agent 编排（M7）：复杂任务（可拆分子任务）走状态机委派并发执行并汇总，
  简单问答直连检索；agent 端点实现父子 run 与委派链查询
- checkpoint 存储切换 LangGraph 原生表（M7）：删除 P2 遗留 ORM checkpoints 表（迁移 0002），
  lineage 走原生 parent_checkpoint_id，决策见 docs/adr/0004-langgraph-checkpoint.md
- 可观测体系（M8）：Tracer(contextvars 传播 trace_id + 嵌套 Span)、SpanCollector 异步批量落库、
  TraceStore 树查询/聚合、Replayer(checkpoint+事件重放)、/traces/* 端点接入实现
- 离线评测（M8）：observability/eval(dataset/metrics/runner/report)、60 条 QA 评测集、
  run_eval.py 统一入口、/eval/* 端点、eval/reports/final_report.md 指标汇总
- 工程化收尾（M8）：Dockerfile multi-stage、CI/CD workflows、deploy/k8s 七清单、
  README 完整化、docs 四件套、ADR 补齐 7 条、demo.py 一键演示、interview_story.md
