# KnowFlow 项目结构

> 来源：由《KnowFlow 项目设计文档》3.3 节抽取，并按大厂工程规范重构
> 版本：v2.0 ｜ 更新：2026-08-05 ｜ 结构变更以本文档为准

## 结构设计原则

- **src 布局**：源码统一放 `src/knowflow/`，与测试/脚本/部署隔离，避免隐式导入路径
- **分层架构**：api(接口层) → services(业务编排) → 领域模块(agents/retrieval/tools/context/sandbox/memory/observability) → repositories(数据访问) → 存储
- **API 版本化**：`/api/v1/` 前缀统一入口，新版本升级不破坏旧客户端
- **任务异步化**：耗时操作（文档解析索引、离线评测）入队由独立 Worker 消费，API 保持快速响应
- **测试分层**：unit(单测，mock 外部依赖) / integration(集成，真实容器依赖) / e2e(端到端)
- **工程化门禁**：CI/CD 流水线 + pre-commit + ruff/mypy 检查 + Makefile 命令入口
- **决策留痕**：`docs/adr/` 记录关键架构取舍（对应设计文档 D1-D7）

## 完整目录树

```
knowflow/
├── .github/                              # ── CI/CD 流水线 ──
│   └── workflows/
│       ├── ci.yml                        # PR 门禁：ruff lint → mypy → pytest(unit/integration) → coverage
│       └── cd.yml                        # main 合并：构建镜像 → 推送 registry → 部署 k8s
├── .dockerignore
├── .editorconfig                         # 跨编辑器格式统一
├── .env.example                          # 环境变量模板（本地开发）
├── .gitignore
├── .pre-commit-config.yaml               # pre-commit hooks：ruff / mypy / 格式检查
├── .python-version                       # 3.13
├── CHANGELOG.md                          # 版本变更记录
├── Dockerfile                            # multi-stage：builder(依赖安装) → runtime(精简镜像)
├── LICENSE
├── Makefile                              # 命令入口：make dev / test / lint / build / up
├── README.md
├── docker-compose.yml                    # 本地依赖：PostgreSQL / Milvus / Redis / MinIO
├── pyproject.toml                        # 依赖声明 + [tool.ruff] [tool.mypy] [tool.pytest] 配置段
├── uv.lock
│
├── src/
│   └── knowflow/
│       ├── __init__.py
│       ├── main.py                       # FastAPI 应用工厂(create_app) + 根路由 + 生命周期
│       │
│       ├── core/                         # ── 核心基础设施层 ──
│       │   ├── __init__.py
│       │   ├── config.py                 # Settings（pydantic-settings，环境变量前缀 KNOWFLOW_）
│       │   ├── constants.py              # 全局常量（执行域类型/任务状态/事件类型/错误码）
│       │   ├── exceptions.py             # 异常体系（AppError 基类 + 子类，错误码映射）
│       │   ├── logging.py                # structlog 结构化日志（JSON 输出）
│       │   ├── lifecycle.py              # 应用生命周期（连接池/后台任务启停）
│       │   └── telemetry.py              # OpenTelemetry 初始化（trace/metric）
│       │
│       ├── db/                           # ── 数据访问层 ──
│       │   ├── __init__.py
│       │   ├── base.py                   # async engine + Session 工厂
│       │   ├── repositories/             # Repository 模式：业务与 SQL 解耦
│       │   │   ├── __init__.py
│       │   │   ├── document_repo.py      # 文档/分块 CRUD
│       │   │   ├── graph_repo.py         # 实体/关系/一跳扩展查询
│       │   │   ├── session_repo.py       # 会话/消息
│       │   │   ├── agent_repo.py         # AgentRun/委派/checkpoint
│       │   │   └── trace_repo.py         # Trace 写入/查询
│       │   ├── redis.py                  # Redis 连接池 + 序列化
│       │   ├── milvus.py                 # Milvus client + collection 生命周期
│       │   ├── minio.py                  # MinIO client
│       │   └── migrations/               # Alembic 迁移
│       │       ├── env.py
│       │       └── versions/
│       │
│       ├── models/                       # ── ORM 模型 ──
│       │   ├── __init__.py
│       │   ├── base.py                   # DeclarativeBase + 公共 Mixin
│       │   ├── document.py               # Document / Chunk / DocumentIndex
│       │   ├── graph.py                  # Entity / Relation / EntityAlias
│       │   ├── session.py                # Session / Message / Turn
│       │   ├── agent.py                  # AgentRun / TaskDelegation / Checkpoint
│       │   ├── tool.py                   # ToolCall / SkillActivation / ToolMetric
│       │   ├── memory.py                 # LongTermMemory / MemorySummary
│       │   ├── trace.py                  # TraceSpan / TraceEvent
│       │   └── eval.py                   # EvalDataset / EvalResult / EvalRun
│       │
│       ├── schemas/                      # ── Pydantic 请求/响应 Schema ──
│       │   ├── __init__.py
│       │   ├── common.py                 # 通用响应/分页/错误
│       │   ├── chat.py                   # ChatRequest / ChatResponse / StreamChunk
│       │   ├── document.py               # UploadResponse / DocumentInfo
│       │   ├── agent.py                  # TaskDelegationSchema / AgentStateSchema
│       │   ├── tool.py                   # ToolSchema / SkillSchema / ToolDomain
│       │   ├── memory.py                 # MemoryItem / MemoryRecallResult
│       │   ├── trace.py                  # TraceQuery / TraceResponse / ReplayRequest
│       │   └── eval.py                   # EvalRequest / EvalReport
│       │
│       ├── api/                          # ── 接口层 ──
│       │   ├── __init__.py
│       │   ├── deps.py                   # 依赖注入（DB Session/当前用户/租户）
│       │   ├── middleware.py             # 鉴权/租户隔离/限流/请求ID/访问日志
│       │   ├── sse.py                    # SSE 流式封装（事件编码/心跳/断线）
│       │   ├── router.py                 # 根路由（挂载 /api/v1 + /health）
│       │   └── v1/                       # API 版本化
│       │       ├── __init__.py
│       │       ├── router.py             # /api/v1 路由聚合
│       │       └── endpoints/            # 每个资源一个模块
│       │           ├── __init__.py
│       │           ├── chat.py           # POST /chat · POST /chat/stream (SSE)
│       │           ├── document.py       # 上传/列表/删除/重建索引
│       │           ├── knowledge.py      # 知识库 CRUD / 检索
│       │           ├── agent.py          # Agent 状态/任务/历史
│       │           ├── skill.py          # Skill 列表/启停/配置
│       │           ├── memory.py         # 记忆查询/删除/压缩
│       │           ├── trace.py          # Trace 查询/会话 replay
│       │           ├── eval.py           # 评测任务/结果报告
│       │           └── health.py         # 健康检查/就绪探针
│       │
│       ├── services/                     # ── 业务服务层（编排领域模块）──
│       │   ├── __init__.py
│       │   ├── chat_service.py           # 对话主流程（编排 Agent/检索/上下文/流式）
│       │   ├── document_service.py       # 文档管理 + 触发索引任务
│       │   ├── knowledge_service.py      # 知识库管理（CRUD/重建/统计）
│       │   ├── agent_service.py          # Agent 管理（状态/任务/历史）
│       │   └── eval_service.py           # 评测服务（任务/报告/对比）
│       │
│       ├── tasks/                        # ── 异步任务定义（由 Worker 消费）──
│       │   ├── __init__.py
│       │   ├── broker.py                 # 任务队列封装（Redis Stream）
│       │   ├── index_task.py             # 文档解析/embedding/实体抽取/入库
│       │   └── eval_task.py              # 评测集执行
│       │
│       ├── agents/                       # ── F3: Multi-Agent 编排层 ──
│       │   ├── __init__.py
│       │   ├── registry.py               # Agent 注册表（主/子 Agent 元信息）
│       │   ├── base.py                   # BaseAgent 抽象（decide/act/observe）
│       │   ├── main_agent.py             # MainAgent（任务规划/委派/汇总）
│       │   ├── subagent.py               # Subagent（子线程隔离执行）
│       │   ├── orchestrator.py           # 编排器（并发调度/结果聚合/超时）
│       │   ├── graph.py                  # LangGraph 状态机定义（节点/边/条件路由）
│       │   ├── state.py                  # AgentState（消息/工具/任务/上下文）
│       │   ├── checkpoint.py             # CheckpointManager（父子关系/序列化/恢复）
│       │   ├── delegation.py             # TaskDelegation（委派协议/父子映射）
│       │   ├── concurrent.py             # 并发执行器（asyncio.gather/超时/降级）
│       │   └── prompts.py                # Agent 系统 Prompt 模板
│       │
│       ├── retrieval/                    # ── F1: GraphRAG 检索模块 ──
│       │   ├── __init__.py
│       │   ├── pipeline.py               # RetrievalPipeline（编排完整检索链路）
│       │   ├── indexer/                  # 文档索引子模块
│       │   │   ├── __init__.py
│       │   │   ├── parser.py             # 文档解析调度（按扩展名分发）
│       │   │   ├── pdf_parser.py         # PDF 解析（PyMuPDF）
│       │   │   ├── docx_parser.py        # DOCX 解析（python-docx）
│       │   │   ├── markdown_parser.py    # Markdown 解析
│       │   │   ├── text_parser.py        # 纯文本解析
│       │   │   ├── splitter.py           # 分块策略（语义/递归/overlap）
│       │   │   └── cleaner.py            # 文本清洗（去噪/规范化）
│       │   ├── embedding.py              # Embedding 客户端（多模型/批量）
│       │   ├── entity_extractor.py       # LLM 实体关系抽取（Prompt/解析/归一）
│       │   ├── graph_store.py            # PostgreSQL 图谱存储（entities/relations CRUD）
│       │   ├── vector_store.py           # Milvus 向量存储（upsert/search/管理）
│       │   ├── bm25_store.py             # BM25 索引（PostgreSQL tsvector / 倒排）
│       │   ├── hybrid_search.py          # Hybrid 融合（RRF / 加权）
│       │   ├── expander.py               # 实体一跳扩展（SQL JOIN 召回关联 chunk）
│       │   ├── reranker.py               # Reranker 精排（cross-encoder / LLM 打分）
│       │   ├── retriever.py              # 统一检索入口（GraphRAGRetriever）
│       │   └── cache.py                  # 检索结果缓存（query hash + TTL）
│       │
│       ├── tools/                        # ── F2: 工具治理模块 ──
│       │   ├── __init__.py
│       │   ├── registry.py               # ToolRegistry（工具注册/查询/元信息）
│       │   ├── base.py                   # BaseTool 抽象（name/desc/schema/execute）
│       │   ├── domain.py                 # 执行域管理（direct/skill_only/subagent_only/internal）
│       │   ├── skill_loader.py           # SkillLoader（YAML frontmatter 解析/加载）
│       │   ├── skill_schema.py           # SkillDefinition 数据模型（元信息/工具/依赖）
│       │   ├── dependency_resolver.py    # 依赖解析（依赖开关/关联工具拓扑排序）
│       │   ├── injector.py               # 动态注入器（按 Skill 激活注入关联工具）
│       │   ├── visibility.py             # 可见性计算（根据执行域过滤模型可见工具）
│       │   ├── permission.py             # 工具权限校验（运行时越权拦截）
│       │   ├── metrics.py                # 工具调用统计（Token/可见数/准确率）
│       │   ├── builtin/                  # 内置工具
│       │   │   ├── __init__.py
│       │   │   ├── retrieval_tool.py     # 知识检索工具
│       │   │   ├── file_tools.py         # 沙盒文件工具（read/write/list）
│       │   │   ├── search_tool.py        # 网络搜索工具
│       │   │   └── calculator.py         # 计算器工具
│       │   └── mcp/                      # MCP 协议接入
│       │       ├── __init__.py
│       │       ├── client.py             # MCPClient（连接/握手/工具发现）
│       │       ├── adapter.py            # MCP 工具适配（转 BaseTool）
│       │       ├── transport.py          # 传输层（stdio/SSE/HTTP）
│       │       └── registry.py           # MCP 服务器注册管理
│       │
│       ├── context/                      # ── F4: 上下文工程模块 ──
│       │   ├── __init__.py
│       │   ├── manager.py                # ContextManager（编排各策略）
│       │   ├── builder.py                # 上下文构建器（系统/历史/工具/记忆组装）
│       │   ├── window.py                 # 滑动窗口（最近 N 轮 + 阈值截断）
│       │   ├── summarizer.py             # 动态摘要（LLM 摘要历史 + 关键信息保留）
│       │   ├── spiller.py                # 卸载机制（超阈值结果写入沙盒 + 引用替换）
│       │   ├── token_counter.py          # Token 计数（tiktoken / 模型特定）
│       │   ├── budget.py                 # 上下文预算管理（分配/超限告警/降级）
│       │   └── strategy.py               # 策略选择（按任务类型选上下文策略）
│       │
│       ├── sandbox/                      # ── F5: 沙盒文件系统模块 ──
│       │   ├── __init__.py
│       │   ├── workspace.py              # WorkspaceManager（会话级隔离/创建/清理）
│       │   ├── virtual_path.py           # 虚拟路径映射（/workspace/xxx → MinIO key）
│       │   ├── file_ops.py               # 文件操作（read/write/list/delete/exists）
│       │   ├── access_control.py         # 访问控制（路径校验/越权拦截/白名单）
│       │   ├── minio_backend.py          # MinIO 存储后端（bucket 管理/对象 CRUD）
│       │   ├── lifecycle.py              # 生命周期（TTL/会话结束清理/配额）
│       │   └── quota.py                  # 配额管理（单会话/单租户容量限制）
│       │
│       ├── memory/                       # ── 记忆模块 ──
│       │   ├── __init__.py
│       │   ├── manager.py                # MemoryManager（编排短期/长期）
│       │   ├── short_term.py             # 短期记忆（Redis · 会话级 · TTL）
│       │   ├── long_term.py              # 长期记忆（PostgreSQL · 跨会话）
│       │   ├── compressor.py             # 记忆压缩（LLM 摘要 + 关键信息提取）
│       │   ├── recall.py                 # 记忆召回（语义相关度 + 时间衰减）
│       │   ├── importance.py             # 重要性评估（打分/筛选/沉淀阈值）
│       │   └── store.py                  # 记忆存储（CRUD + 索引）
│       │
│       └── observability/                # ── 可观测/评测模块 ──
│           ├── __init__.py
│           ├── tracer.py                 # Tracer（Span 创建/嵌套/上下文传播）
│           ├── span.py                   # TraceSpan 数据模型（决策/工具/检索）
│           ├── collector.py              # Trace 收集器（异步写入/批量刷新）
│           ├── store.py                  # Trace 存储（PostgreSQL + 查询索引）
│           ├── replay.py                 # 会话 Replay（按 checkpoint + trace 回放）
│           ├── eval/                     # 离线评测子模块
│           │   ├── __init__.py
│           │   ├── runner.py             # EvalRunner（跑评测集/对比 baseline）
│           │   ├── dataset.py            # 评测集管理（加载/标注/版本）
│           │   ├── metrics.py            # 指标计算（Recall@K/MRR/NDCG/准确率）
│           │   └── report.py             # 评测报告生成
│           └── dashboard.py              # 可观测数据聚合（调用统计/性能指标）
│
├── worker/                               # ── 独立 Worker 进程（与 API 分离部署）──
│   ├── __init__.py
│   ├── main.py                           # 启动入口（消费 tasks 队列）
│   └── settings.py                       # Worker 专用配置（模型/批量参数）
│
├── skills/                               # ── Skill 声明式定义（YAML）──
│   ├── knowledge_qa/                     # 知识问答技能
│   │   ├── SKILL.md                      # YAML frontmatter + 描述
│   │   └── config.yml
│   ├── document_summary/                 # 文档摘要技能
│   │   └── SKILL.md
│   ├── data_analysis/                    # 数据分析技能
│   │   └── SKILL.md
│   └── code_review/                      # 代码审查技能
│       └── SKILL.md
│
├── tests/                                # ── 测试（分层）──
│   ├── conftest.py                       # 公共 fixtures（测试库/Redis/Milvus/MinIO mock）
│   ├── unit/                             # 单测（mock 外部存储，不依赖容器）
│   │   ├── retrieval/
│   │   │   ├── test_splitter.py
│   │   │   ├── test_entity_extractor.py
│   │   │   ├── test_graph_store.py
│   │   │   ├── test_hybrid_search.py
│   │   │   ├── test_expander.py
│   │   │   └── test_reranker.py
│   │   ├── tools/
│   │   │   ├── test_skill_loader.py
│   │   │   ├── test_domain.py
│   │   │   ├── test_visibility.py
│   │   │   └── test_dependency_resolver.py
│   │   ├── agents/
│   │   │   ├── test_orchestrator.py
│   │   │   ├── test_checkpoint.py
│   │   │   └── test_concurrent.py
│   │   ├── context/
│   │   │   ├── test_window.py
│   │   │   ├── test_summarizer.py
│   │   │   └── test_spiller.py
│   │   ├── sandbox/
│   │   │   └── test_workspace.py
│   │   └── memory/
│   │       ├── test_long_term.py
│   │       └── test_recall.py
│   ├── integration/                     # 集成测试（真实容器依赖）
│   │   ├── test_chat_flow.py            # 端到端对话
│   │   ├── test_index_pipeline.py       # 文档索引全链路
│   │   └── test_multi_agent.py          # 多 Agent 编排
│   ├── e2e/                              # 端到端（完整服务 + 真实模型）
│   │   └── test_chat_stream_e2e.py      # SSE 流式全链路
│   └── eval/
│       └── test_rag_eval.py             # RAG 评测验证
│
├── eval/                                 # ── 评测数据集与脚本 ──
│   ├── datasets/
│   │   ├── knowledge_qa_eval.jsonl       # 知识问答评测集
│   │   └── retrieval_eval.jsonl          # 检索召回评测集
│   └── scripts/
│       ├── run_eval.py                   # 跑评测
│       └── compare_baseline.py           # baseline 对比
│
├── scripts/                              # ── 工程脚本 ──
│   ├── init_db.py                        # 初始化数据库 + 图谱表
│   ├── init_milvus.py                    # 创建 Milvus collection
│   ├── seed_skills.py                    # 加载默认 Skill
│   ├── benchmark.py                      # 性能基准测试
│   └── gen_openapi.py                    # 生成 OpenAPI 文档
│
├── deploy/                               # ── 部署清单 ──
│   ├── k8s/
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.example.yaml
│   │   ├── api-deployment.yaml
│   │   ├── api-service.yaml
│   │   ├── worker-deployment.yaml
│   │   └── hpa.yaml                      # 水平扩缩容
│   └── README.md
│
└── docs/                                 # ── 项目文档 ──
    ├── adr/                              # 架构决策记录（ADR）：对应设计文档 D1-D7
    │   ├── README.md
    │   ├── 0001-graph-store-postgres.md
    │   └── 0002-sse-over-websocket.md
    ├── architecture.md                   # 架构详述
    ├── api_reference.md                  # API 接口文档
    ├── skill_development.md              # Skill 开发指南
    └── deployment.md                     # 部署指南
```

## 文件规模统计

- 核心源码（src/knowflow/）：约 110 个文件
- Worker 独立进程：3 个文件
- 测试：约 23 个文件（unit 19 + integration 3 + e2e 1 + eval 1）
- 配置/CI/CD/部署/脚本/文档：约 35 个文件
- 总计：约 170 个文件，每个文件单一职责

## 与 v1.0 结构的差异说明

| 变更 | 原结构 | 新结构 | 原因 |
|---|---|---|---|
| API 版本化 | `api/routes/` | `api/v1/endpoints/` + router 聚合 | 多版本共存，升级不破坏客户端 |
| 数据访问 | 直接调用 DB | Repository 模式（`db/repositories/`） | 业务与 SQL 解耦，便于单测 mock |
| 异步任务 | 无 | `tasks/` + `worker/` 独立进程 | 文档索引/评测耗时长，API 不阻塞 |
| CI/CD | 无 | `.github/workflows/` | 代码质量门禁 + 自动化发布 |
| 工程化配置 | 无 | pre-commit / Makefile / .editorconfig / multi-stage Dockerfile | 团队协作规范 |
| 部署 | 仅 docker-compose | 增加 `deploy/k8s/` | 生产级部署清单 |
| 决策留痕 | 设计文档 D1-D7 | `docs/adr/` | 架构决策入库，可追溯 |
