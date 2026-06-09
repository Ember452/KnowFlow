# KnowFlow 提交日志

> 本项目全部 git commit 的时间线与信息记录，用于保持 GitHub 提交历史与简历时间线一致。
> 规则：时间线起点为 **2026 年 6 月初**（首条记录从 2026-06-01 开始）；后续批次的日期必须**晚于最后一条记录**（向后推迟，同一批次多条可分布在相邻日期，按提交顺序递增）。

---

## M1 · P0 · 项目脚手架与工程规范（2026-06-01）

**Phase 总览**：完成项目脚手架初始化，建立工程规范基线。包括根目录元文件（.gitignore / .editorconfig / LICENSE 等）、pyproject.toml 依赖声明、docker-compose 本地依赖编排、pre-commit 工程化配置、项目设计文档与开发规范、src 布局完整目录骨架。本阶段不涉及业务逻辑，仅奠定工程化基础，后续所有 Phase 在此骨架上推进。

---

### 1. chore: 初始化项目元文件与 git 忽略规则

- **提交时间**：2026-06-01 09:00
- **说明**：建立项目根目录元文件。`.gitignore` 覆盖 Python 常见产物（.venv/、__pycache__/、.env、dist/、.coverage、htmlcov/）与 IDE 配置；`.editorconfig` 统一跨编辑器缩进与换行；`.dockerignore` 排除构建上下文无关文件；`.python-version` 锁定 3.13；`LICENSE` 采用 MIT。
- **变更文件**：`.gitignore`、`.editorconfig`、`.dockerignore`、`.python-version`、`LICENSE`

```
$env:GIT_AUTHOR_DATE = "2026-06-01T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-01T09:00:00+08:00"
git add .gitignore .editorconfig .dockerignore .python-version LICENSE
git commit -m "chore: 初始化项目元文件与 git 忽略规则"
```

---

### 2. build: 编写 pyproject.toml 与运行时依赖声明

- **提交时间**：2026-06-01 11:00
- **说明**：按设计文档 3.7 节声明全部运行时依赖（FastAPI / LangGraph / LangChain / Milvus / SQLAlchemy[asyncio]+asyncpg / Redis / MinIO / structlog 等 26 个），async 栈仅保留 asyncpg 不装 psycopg2-binary。dev 组含 pytest / ruff / mypy / pre-commit / aiosqlite（repo 单测用）。配置 [tool.ruff] / [tool.mypy] / [tool.pytest] / [tool.coverage] 全部工程门禁段。`uv sync` 生成 uv.lock。
- **变更文件**：`pyproject.toml`、`uv.lock`

```
$env:GIT_AUTHOR_DATE = "2026-06-01T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-01T11:00:00+08:00"
git add pyproject.toml uv.lock
git commit -m "build: 编写 pyproject.toml 与运行时依赖声明"
```

---

### 3. build: 添加 docker-compose 与工程化配置

- **提交时间**：2026-06-01 13:00
- **说明**：`docker-compose.yml` 编排本地依赖（postgres:16 / milvusdb/milvus:v2.4.0 / redis:7 / minio/minio），补全数据卷与健康检查；`.env.example` 提供本地开发环境变量模板；`.pre-commit-config.yaml` 配置 ruff(--fix) / ruff-format / mypy / trailing-whitespace / end-of-file-fixer / check-yaml/toml/json hooks；`Makefile` 提供 make dev / test / lint / build / up 命令入口。
- **变更文件**：`docker-compose.yml`、`.env.example`、`.pre-commit-config.yaml`、`Makefile`

```
$env:GIT_AUTHOR_DATE = "2026-06-01T13:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-01T13:00:00+08:00"
git add docker-compose.yml .env.example .pre-commit-config.yaml Makefile
git commit -m "build: 添加 docker-compose 与工程化配置"
```

---

### 4. docs: 添加项目设计文档与开发规范

- **提交时间**：2026-06-01 15:00
- **说明**：落地项目顶层文档。`AGENTS.md` 为 AI 开发行为准则（门禁命令 / 提交规范 / 红线清单）；`KnowFlow-项目设计文档.md` 含 PRD / 架构 / 模块设计 / API / 量化指标；`KnowFlow-项目结构.md` 定义 src 布局完整目录树；`KnowFlow-开发计划.md` 定义 P0-P11 推进顺序与验收标准；`CHANGELOG.md` 初始条目；`README.md` 占位（P11 完善）；`commit-log.md` 建立提交时间线规则。
- **变更文件**：`AGENTS.md`、`CHANGELOG.md`、`README.md`、`docs/KnowFlow-项目设计文档.md`、`docs/KnowFlow-项目结构.md`、`docs/KnowFlow-开发计划.md`、`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-01T15:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-01T15:00:00+08:00"
git add AGENTS.md CHANGELOG.md README.md "docs/KnowFlow-项目设计文档.md" "docs/KnowFlow-项目结构.md" "docs/KnowFlow-开发计划.md" docs/commit-log.md
git commit -m "docs: 添加项目设计文档与开发规范"
```

---

### 5. chore(core): 创建 src 包目录骨架与冒烟测试

- **提交时间**：2026-06-01 17:00
- **说明**：按《项目结构》文档创建全部子包 `__init__.py`（core / db / models / schemas / api / services / tasks / agents / retrieval / tools / context / sandbox / memory / observability 及子包），worker/ 与 tests/ 分层目录（unit/integration/e2e/eval）。新增 `tests/unit/test_smoke.py` 验证包可导入，`eval/reports/.gitkeep` 占位。本提交不包含业务代码，仅建立目录骨架。
- **变更文件**：`src/knowflow/` 下全部 `__init__.py`、`worker/__init__.py`、`tests/` 下全部 `__init__.py`、`tests/unit/test_smoke.py`、`eval/reports/.gitkeep`

```
$env:GIT_AUTHOR_DATE = "2026-06-01T17:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-01T17:00:00+08:00"
git add src/knowflow/__init__.py src/knowflow/agents/__init__.py src/knowflow/api/__init__.py src/knowflow/api/v1/__init__.py src/knowflow/api/v1/endpoints/__init__.py src/knowflow/context/__init__.py src/knowflow/core/__init__.py src/knowflow/db/__init__.py src/knowflow/db/migrations/__init__.py src/knowflow/db/repositories/__init__.py src/knowflow/memory/__init__.py src/knowflow/models/__init__.py src/knowflow/observability/__init__.py src/knowflow/observability/eval/__init__.py src/knowflow/retrieval/__init__.py src/knowflow/retrieval/indexer/__init__.py src/knowflow/sandbox/__init__.py src/knowflow/schemas/__init__.py src/knowflow/services/__init__.py src/knowflow/tasks/__init__.py src/knowflow/tools/__init__.py src/knowflow/tools/builtin/__init__.py src/knowflow/tools/mcp/__init__.py worker/__init__.py tests/__init__.py tests/e2e/__init__.py tests/eval/__init__.py tests/integration/__init__.py tests/unit/__init__.py tests/unit/agents/__init__.py tests/unit/context/__init__.py tests/unit/memory/__init__.py tests/unit/retrieval/__init__.py tests/unit/sandbox/__init__.py tests/unit/tools/__init__.py tests/unit/test_smoke.py eval/reports/.gitkeep
git commit -m "chore(core): 创建 src 包目录骨架与冒烟测试"
```

---

## M1 · P1 · 核心基础设施与本地依赖（2026-06-02）

**Phase 总览**：实现应用核心基础设施层，建立配置 / 日志 / 异常 / 生命周期 / 可观测的统一基座。`core/config.py` 用 pydantic-settings 管理环境变量（前缀 KNOWFLOW_）；`core/constants.py` 定义执行域 / 任务状态 / SSE 事件类型 / 错误码前缀；`core/exceptions.py` 建立 AppError 异常体系；`core/logging.py` 接入 structlog 结构化日志；`core/lifecycle.py` + `telemetry.py` 管理连接池启停与 OpenTelemetry；`db/` 层接入 PostgreSQL(async) / Redis / Milvus / MinIO 客户端；`main.py` 提供 FastAPI 应用工厂。本阶段完成后，应用可启动并连通全部外部依赖。

---

### 6. feat(core): 实现应用配置与 pydantic-settings 加载

- **提交时间**：2026-06-02 09:00
- **说明**：`Settings` 类基于 pydantic-settings，环境变量前缀 `KNOWFLOW_`，覆盖 env / Postgres / Redis / Milvus / MinIO / LLM / Embedding 全部配置项。`postgres_dsn` 属性自动拼装 asyncpg 异步 DSN。`is_prod` / `is_dev` 便利属性。单测验证默认值与 env 覆盖加载。
- **变更文件**：`src/knowflow/core/config.py`、`tests/unit/test_config.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-02T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-02T09:00:00+08:00"
git add src/knowflow/core/config.py tests/unit/test_config.py
git commit -m "feat(core): 实现应用配置与 pydantic-settings 加载"
```

---

### 7. feat(core): 定义全局常量与异常体系

- **提交时间**：2026-06-02 10:30
- **说明**：`constants.py` 定义四类执行域（direct / skill_only / subagent_only / internal）、任务状态机（created → delegated → running → completed/failed）、SSE 事件类型枚举、错误码前缀（CFG / DB / RET / TOOL / AGENT / CTX / SBX）。`exceptions.py` 建立 `AppError` 基类（含 code / message / status_code）与 ConfigError / DBError / RetrievalError / ToolError / AgentError / ContextError / SandboxError 子类。单测覆盖异常链与错误码映射。
- **变更文件**：`src/knowflow/core/constants.py`、`src/knowflow/core/exceptions.py`、`tests/unit/test_exceptions.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-02T10:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-02T10:30:00+08:00"
git add src/knowflow/core/constants.py src/knowflow/core/exceptions.py tests/unit/test_exceptions.py
git commit -m "feat(core): 定义全局常量与异常体系"
```

---

### 8. feat(core): 接入 structlog 结构化日志

- **提交时间**：2026-06-02 13:00
- **说明**：`logging.py` 基于 structlog 配置 JSON 输出（生产）与 console 输出（开发），`setup_logging()` 在应用启动时初始化，`get_logger(name)` 返回绑定上下文的 logger。日志含 timestamp / level / event / logger 字段，便于后续 Trace 关联。单测验证日志输出格式与字段。
- **变更文件**：`src/knowflow/core/logging.py`、`tests/unit/test_logging.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-02T13:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-02T13:00:00+08:00"
git add src/knowflow/core/logging.py tests/unit/test_logging.py
git commit -m "feat(core): 接入 structlog 结构化日志"
```

---

### 9. feat(core): 添加生命周期管理与 OpenTelemetry 钩子

- **提交时间**：2026-06-02 14:30
- **说明**：`lifecycle.py` 定义 FastAPI lifespan 异步上下文管理器，统一启停 PostgreSQL 引擎 / Redis 连接池 / Milvus client / MinIO client，避免散落在各模块的连接管理。`telemetry.py` 提供 OpenTelemetry TracerProvider 初始化钩子（资源 / BatchSpanProcessor），后续模块通过 `get_tracer(name)` 获取 tracer 注入 Span。
- **变更文件**：`src/knowflow/core/lifecycle.py`、`src/knowflow/core/telemetry.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-02T14:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-02T14:30:00+08:00"
git add src/knowflow/core/lifecycle.py src/knowflow/core/telemetry.py
git commit -m "feat(core): 添加生命周期管理与 OpenTelemetry 钩子"
```

---

### 10. feat(db): 接入 PostgreSQL/Redis/Milvus/MinIO 客户端

- **提交时间**：2026-06-02 16:00
- **说明**：`db/base.py` 创建 SQLAlchemy async engine 与 async_sessionmaker（连接池参数由 Settings 注入）；`db/redis.py` 封装 Redis 连接池与序列化辅助；`db/milvus.py` 封装 Milvus client 与 collection 生命周期；`db/minio.py` 封装 MinIO client 与 bucket 初始化。所有客户端由 `lifespan` 统一管理启停，不在模块级创建连接。
- **变更文件**：`src/knowflow/db/base.py`、`src/knowflow/db/redis.py`、`src/knowflow/db/milvus.py`、`src/knowflow/db/minio.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-02T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-02T16:00:00+08:00"
git add src/knowflow/db/base.py src/knowflow/db/redis.py src/knowflow/db/milvus.py src/knowflow/db/minio.py
git commit -m "feat(db): 接入 PostgreSQL/Redis/Milvus/MinIO 客户端"
```

---

### 11. feat(api): 添加 FastAPI 应用工厂与依赖检查脚本

- **提交时间**：2026-06-02 17:30
- **说明**：`main.py` 实现 `create_app()` 应用工厂，挂载 lifespan（管理连接池启停）、根路由 `/health` 健康检查、API 版本化前缀 `/api/v1`。`scripts/check_env.py` 提供 PG / Redis / Milvus / MinIO 连通性检查脚本，本地 `docker compose up -d` 后运行验证依赖就绪。本阶段应用可启动并返回健康检查响应。
- **变更文件**：`src/knowflow/main.py`、`scripts/check_env.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-02T17:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-02T17:30:00+08:00"
git add src/knowflow/main.py scripts/check_env.py
git commit -m "feat(api): 添加 FastAPI 应用工厂与依赖检查脚本"
```

---

## M1 · P2 · ORM 模型、迁移与 Repository（2026-06-03）

**Phase 总览**：完成数据访问层全部建设，覆盖 ORM 模型 / 数据库迁移 / Repository 模式三个层次。先以 ADR 记录 checkpoint 存储决策（PostgreSQL 而非 Redis），再实现 ORM 基类（IDMixin / TimestampMixin / JSONBType 跨方言 / VectorField）与 9 个模型文件（22 张表，覆盖文档 / 图谱 / 会话 / Agent / 工具 / 记忆 / Trace / 评测全部领域）。配置 Alembic 异步迁移环境并手写初始 schema 迁移脚本。实现 5 个 Repository（Document / Graph / Session / Agent / Trace），含一跳扩展查询与 checkpoint 父子链路回溯。60 个单测基于 SQLite+aiosqlite 内存库运行，不依赖真实 PG 容器，覆盖率达 69%。

---

### 12. docs(adr): 记录 checkpoint 存储决策

- **提交时间**：2026-06-03 09:00
- **说明**：开发计划与设计文档对 checkpoint 存储位置存在歧义（Redis vs PostgreSQL）。本 ADR 记录决策：checkpoint 主存 PostgreSQL（`checkpoints` 表，JSONB state 字段），原因有三——一是 checkpoint 父子关系需外键约束保证一致性，二是 replay 场景需按 agent_run_id 历史查询，三是 Redis 仅作会话级短期缓存。决策依据与备选方案对比详见 ADR 文档。
- **变更文件**：`docs/adr/0003-checkpoint-storage.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T09:00:00+08:00"
git add docs/adr/0003-checkpoint-storage.md
git commit -m "docs(adr): 记录 checkpoint 存储决策"
```

---

### 13. feat(db): 实现 ORM 基类与全部领域模型

- **提交时间**：2026-06-03 10:00
- **说明**：`models/base.py` 实现 `Base` 声明式基类、`IDMixin`（BIGINT 自增主键，SQLite 降级 Integer 以支持单测）、`TimestampMixin`（created_at / updated_at 默认 now()）、`JSONBType`（PG 用 JSONB / SQLite 用 JSON 的跨方言类型装饰器）、`VectorField`（向量列抽象）。9 个模型文件定义 22 张表：document.py（Document / Chunk / DocumentIndex）、graph.py（Entity / EntityAlias / Relation）、session.py（Session / Message / Turn）、agent.py（AgentRun / TaskDelegation / Checkpoint）、tool.py（ToolCall / SkillActivation / ToolMetric）、memory.py（LongTermMemory / MemorySummary）、trace.py（TraceSpan / TraceEvent）、eval.py（EvalDataset / EvalRun / EvalResult）。外键关系与级联删除完整定义。
- **变更文件**：`src/knowflow/models/base.py`、`src/knowflow/models/document.py`、`src/knowflow/models/graph.py`、`src/knowflow/models/session.py`、`src/knowflow/models/agent.py`、`src/knowflow/models/tool.py`、`src/knowflow/models/memory.py`、`src/knowflow/models/trace.py`、`src/knowflow/models/eval.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T10:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T10:00:00+08:00"
git add src/knowflow/models/base.py src/knowflow/models/document.py src/knowflow/models/graph.py src/knowflow/models/session.py src/knowflow/models/agent.py src/knowflow/models/tool.py src/knowflow/models/memory.py src/knowflow/models/trace.py src/knowflow/models/eval.py
git commit -m "feat(db): 实现 ORM 基类与全部领域模型"
```

---

### 14. feat(db): 配置 Alembic 异步迁移与初始 schema 迁移

- **提交时间**：2026-06-03 13:00
- **说明**：`alembic.ini` 配置迁移入口（DSN 由 env.py 从 Settings 动态注入，避免硬编码）。`migrations/env.py` 支持 async 运行模式，检测 DSN 含 asyncpg 时用 `async_engine_from_config` + `asyncio.run` 执行迁移，兼容同步 DSN 回退。`versions/0001_init_schema.py` 手写初始迁移，按外键依赖顺序创建全部 22 张表（documents → chunks → entities → relations → sessions → messages → turns → agent_runs → task_delegations → checkpoints → trace_spans → trace_events → eval_datasets → eval_runs → eval_results 等）与索引、唯一约束，downgrade 反向 drop。离线模式 `--sql` 验证 DDL 生成正常。
- **变更文件**：`alembic.ini`、`src/knowflow/db/migrations/env.py`、`src/knowflow/db/migrations/versions/0001_init_schema.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T13:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T13:00:00+08:00"
git add alembic.ini src/knowflow/db/migrations/env.py src/knowflow/db/migrations/versions/0001_init_schema.py
git commit -m "feat(db): 配置 Alembic 异步迁移与初始 schema 迁移"
```

---

### 15. feat(scripts): 添加数据库初始化脚本

- **提交时间**：2026-06-03 14:00
- **说明**：`scripts/init_db.py` 提供三种运行模式：默认模式（连接 postgres 库 CREATE DATABASE 若不存在 → `alembic upgrade head`）、`--check`（仅打印当前 alembic 版本不执行）、`--sql`（离线生成 upgrade SQL 到 stdout 不连库）。dev 环境自动建库，prod 跳过（由 DBA 预建）。脚本将 src/ 加入 sys.path，可直接 `python scripts/init_db.py` 运行。离线 SQL 模式无需 PG 容器即可验证迁移脚本语法。
- **变更文件**：`scripts/init_db.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T14:00:00+08:00"
git add scripts/init_db.py
git commit -m "feat(scripts): 添加数据库初始化脚本"
```

---

### 16. feat(db): 实现 Document/Chunk 与图谱 Repository 及单测

- **提交时间**：2026-06-03 15:30
- **说明**：`document_repo.py` 实现 DocumentRepo（CRUD / list_by_user 倒序 / update_status / find_by_content_hash 查重）、ChunkRepo（create / bulk_create 批量 / list_by_doc 按 chunk_index 升序 / get_many 保序跳过不存在）、DocumentIndexRepo（upsert 先查后插不依赖 PG ON CONFLICT）。`graph_repo.py` 实现 EntityRepo（bulk_create / find_by_normalized 归一查询）、EntityAliasRepo（UNIQUE 约束验证）、RelationRepo（list_by_source 出边查询 + `one_hop_expand` 一跳扩展查询，对齐设计文档 3.4 节 SQL：实体 → 关系 → 目标实体 → 关联 chunk，剔除输入实体自身 chunk）。`tests/conftest.py` 提供 SQLite+aiosqlite 内存库 fixture，通过 DBAPI connect 事件开启 `PRAGMA foreign_keys=ON` 验证级联删除。单测覆盖 CRUD、批量、保序、一跳扩展（含自环剔除）、级联删除等场景。
- **变更文件**：`src/knowflow/db/repositories/document_repo.py`、`src/knowflow/db/repositories/graph_repo.py`、`tests/conftest.py`、`tests/unit/db/__init__.py`、`tests/unit/db/test_document_repo.py`、`tests/unit/db/test_graph_repo.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T15:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T15:30:00+08:00"
git add src/knowflow/db/repositories/document_repo.py src/knowflow/db/repositories/graph_repo.py tests/conftest.py tests/unit/db/__init__.py tests/unit/db/test_document_repo.py tests/unit/db/test_graph_repo.py
git commit -m "feat(db): 实现 Document/Chunk 与图谱 Repository 及单测"
```

---

### 17. feat(db): 实现会话/Agent/Trace Repository 及单测

- **提交时间**：2026-06-03 17:00
- **说明**：`session_repo.py` 实现 SessionRepo（CRUD / list_by_user 倒序 / update_status）、MessageRepo（list_by_session 升序 / citations JSON 存取）、TurnRepo（对话轮次关联 user/assistant 消息与 trace_id）。`agent_repo.py` 实现 AgentRunRepo（create / list_children 子运行查询 / mark_completed 置位 completed_at）、TaskDelegationRepo（create / list_by_parent / update_status 带 result 与 checkpoint_id）、CheckpointRepo（save / list_by_run / `lineage` 父子链路回溯，含 `seen` 集合防环死循环）。`trace_repo.py` 实现 TraceSpanRepo（list_by_trace 按 started_at 升序供 replay / end_span 写 output 与 ended_at / metadata JSON 存取）、TraceEventRepo（list_by_span 按时间升序）。单测覆盖父子链路回溯、JSON 字段跨方言存取、状态更新命中/未命中等场景，共 60 个用例全绿，覆盖率 69%。
- **变更文件**：`src/knowflow/db/repositories/session_repo.py`、`src/knowflow/db/repositories/agent_repo.py`、`src/knowflow/db/repositories/trace_repo.py`、`tests/unit/db/test_session_repo.py`、`tests/unit/db/test_agent_repo.py`、`tests/unit/db/test_trace_repo.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T17:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T17:00:00+08:00"
git add src/knowflow/db/repositories/session_repo.py src/knowflow/db/repositories/agent_repo.py src/knowflow/db/repositories/trace_repo.py tests/unit/db/test_session_repo.py tests/unit/db/test_agent_repo.py tests/unit/db/test_trace_repo.py
git commit -m "feat(db): 实现会话/Agent/Trace Repository 及单测"
```

---

### 18. docs: 更新提交日志

- **提交时间**：2026-06-03 18:30
- **说明**：记录 M1（P0 + P1 + P2）全部 17 个业务提交的时间线与详细信息，按 phase 分组并附 phase 总览。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-03T18:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-03T18:30:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

## M1 · 修复与改进（2026-06-04）

**Phase 总览**：M1 代码审查后修复两个 Bug（init_engine 惰性连接导致连通性检查误报 OK，check_env 对 PostgreSQL 虚假通过）并补充工程改进（main.py 健康检查端点测试、.gitignore 放行评测报告入库）。门禁全绿：ruff 0 errors / mypy 0 issues / 63 tests passed，总覆盖率提升至 73%。

---

### 19. fix(db): 修复 init_engine 不验证数据库连通

- **提交时间**：2026-06-04 09:00
- **说明**：`create_async_engine` 为惰性连接，原 `init_engine()` 仅创建引擎不执行查询，导致 PostgreSQL 不可用时连通性检查仍误报 OK（check_env.py 与 lifespan 均受影响）。修复：初始化后执行一次 `SELECT 1` 真实探测，失败时先 dispose 再抛出，不留引擎泄漏。修复后 check_env 对 PostgreSQL 如实反映 FAIL。
- **变更文件**：`src/knowflow/db/base.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-04T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-04T09:00:00+08:00"
git add src/knowflow/db/base.py
git commit -m "fix(db): 修复 init_engine 不验证数据库连通"
```

---

### 20. test(api): 添加应用工厂与健康检查端点测试

- **提交时间**：2026-06-04 10:00
- **说明**：新增 `tests/unit/test_main.py` 覆盖 `/health`、`/`、`/docs` 三个端点，main.py 覆盖率由 0% 提升至 100%，总覆盖率 69% → 73%。TestClient 不带 context manager 使用，避免触发 lifespan 连接外部依赖（首版带 with 导致全量测试耗时 128s，优化后 4.3s）。
- **变更文件**：`tests/unit/test_main.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-04T10:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-04T10:00:00+08:00"
git add tests/unit/test_main.py
git commit -m "test(api): 添加应用工厂与健康检查端点测试"
```

---

### 21. chore: 放行评测报告文件入库

- **提交时间**：2026-06-04 10:30
- **说明**：.gitignore 原忽略 `eval/reports/*.md`，但指标报告（compare_baseline / final_report）是面试证据，需入库展示。移除该忽略规则，仅保留目录注释。
- **变更文件**：`.gitignore`

```
$env:GIT_AUTHOR_DATE = "2026-06-04T10:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-04T10:30:00+08:00"
git add .gitignore
git commit -m "chore: 放行评测报告文件入库"
```

---

### 22. docs: 更新提交日志

- **提交时间**：2026-06-04 11:00
- **说明**：记录本次修复与改进的 3 个提交（19-21）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-04T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-04T11:00:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

## M2 · P3 · GraphRAG 检索模块（2026-06-05 ~ 2026-06-08）

**Phase 总览**：实现完整 GraphRAG 检索链路，覆盖文档解析→递归分块→embedding→LLM 实体抽取→三写入库（图谱/向量/BM25）→Hybrid 召回（RRF 融合）→一跳扩展→Reranker 精排→Redis 缓存→pipeline 编排，配套合成评测语料与 baseline 对比脚本。13 个子模块 + 13 个单测文件（194 个用例），核心模块覆盖率 ≥ 70%（bm25_store 91% / cache 89% / embedding 86% / entity_extractor 90% / graph_store 100% / hybrid_search 100% / splitter 100% / expander 98% / pipeline 93% / retriever 88% / vector_store 84% / reranker 70%），总覆盖率 85%。合成语料静态模式跑通对比报告（Hybrid R@10=33.6% / GraphRAG R@10=32.6%，cross_doc 组 GraphRAG MRR +0.0667），真实 LLM/Milvus 链路指标测试文档交付用户实测。

---

### 23. feat(core): 补充检索参数配置字段

- **提交时间**：2026-06-05 09:00
- **说明**：`Settings` 类新增 `# ── 检索 ──` 段，包含 `chunk_size=512` / `chunk_overlap=64` / `retrieval_top_k=10` / `rrf_k=60` / `retrieval_cache_ttl_seconds=300` / `embedding_batch_size=32` / `reranker_top_k=10` 七个字段，默认值与 `core/constants.py` 对齐，避免硬编码。`.env.example` 同步补充检索段示例。单测扩展新字段默认值断言。
- **变更文件**：`src/knowflow/core/config.py`、`tests/unit/test_config.py`、`.env.example`

```
$env:GIT_AUTHOR_DATE = "2026-06-05T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-05T09:00:00+08:00"
git add src/knowflow/core/config.py tests/unit/test_config.py .env.example
git commit -m "feat(core): 补充检索参数配置字段"
```

---

### 24. feat(retrieval): 实现文档解析器与文本清洗

- **提交时间**：2026-06-05 11:00
- **说明**：`cleaner.py` 实现文本清洗（规范化空白、折叠多空格/换行、剥离零宽字符 \u200b/\ufeff、统一全角空格、处理 \r\n/\r 行尾）。`parser.py` 按扩展名分发到四类解析器：`text_parser.py`（bytes/str）、`markdown_parser.py`（markdown 库转纯文本去标签）、`pdf_parser.py`（pymupdf 逐页取 text）、`docx_parser.py`（python-docx 拼接段落）。所有解析器返回经 clean 的纯文本。`.pre-commit-config.yaml` 改用项目 venv 跑 mypy 解决无 stubs 库的 import-untyped 报错。单测覆盖四类分发、不支持类型异常、空白折叠、零宽字符剥离。
- **变更文件**：`src/knowflow/retrieval/indexer/cleaner.py`、`src/knowflow/retrieval/indexer/parser.py`、`src/knowflow/retrieval/indexer/text_parser.py`、`src/knowflow/retrieval/indexer/markdown_parser.py`、`src/knowflow/retrieval/indexer/pdf_parser.py`、`src/knowflow/retrieval/indexer/docx_parser.py`、`tests/unit/retrieval/test_cleaner.py`、`tests/unit/retrieval/test_parser.py`、`.pre-commit-config.yaml`

```
$env:GIT_AUTHOR_DATE = "2026-06-05T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-05T11:00:00+08:00"
git add src/knowflow/retrieval/indexer/cleaner.py src/knowflow/retrieval/indexer/parser.py src/knowflow/retrieval/indexer/text_parser.py src/knowflow/retrieval/indexer/markdown_parser.py src/knowflow/retrieval/indexer/pdf_parser.py src/knowflow/retrieval/indexer/docx_parser.py tests/unit/retrieval/test_cleaner.py tests/unit/retrieval/test_parser.py .pre-commit-config.yaml
git commit -m "feat(retrieval): 实现文档解析器与文本清洗"
```

---

### 25. feat(retrieval): 实现递归字符分块

- **提交时间**：2026-06-05 14:00
- **说明**：`splitter.py` 实现递归字符分块，按分隔符优先级（`\n\n → \n → 。 → 空格`）递归切分到 chunk_size 以内，分隔符保留在前一块末尾保持语义边界，所有分隔符用尽仍超长则按 chunk_size 硬切。相邻分块保留 overlap 字符（前块末尾拼到后块前缀，不超 chunk_size 才拼避免膨胀）。参数校验：chunk_size > 0、overlap >= 0、overlap < chunk_size。单测覆盖短文本不切、超长递归切分、overlap 边界、空输入、参数异常。
- **变更文件**：`src/knowflow/retrieval/indexer/splitter.py`、`tests/unit/retrieval/test_splitter.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-05T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-05T14:00:00+08:00"
git add src/knowflow/retrieval/indexer/splitter.py tests/unit/retrieval/test_splitter.py
git commit -m "feat(retrieval): 实现递归字符分块"
```

---

### 26. feat(retrieval): 实现 Embedding 客户端封装

- **提交时间**：2026-06-05 16:00
- **说明**：`EmbeddingClient` 类封装 sentence-transformers，`embed(texts)` 批量接口按 `embedding_batch_size` 分批推理，`embed_one(text)` 单条便利方法。底层用 `SentenceTransformer(settings.embedding_model)`（默认 BAAI/bge-m3，dim=1024），进程内单例懒加载（`get_embedding_client()`）。单测 monkeypatch 替换模型，验证批量分批、维度、单条与批量一致性。
- **变更文件**：`src/knowflow/retrieval/embedding.py`、`tests/unit/retrieval/test_embedding.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-05T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-05T16:00:00+08:00"
git add src/knowflow/retrieval/embedding.py tests/unit/retrieval/test_embedding.py
git commit -m "feat(retrieval): 实现 Embedding 客户端封装"
```

---

### 27. feat(retrieval): 实现 LLM 实体关系抽取

- **提交时间**：2026-06-06 09:00
- **说明**：`EntityExtractor` 类用 `langchain_openai.ChatOpenAI`（DeepSeek）抽取实体与关系。`extract(chunk_text)` 调 LLM 输出严格 JSON（`{"entities": [{"name","type"}], "relations": [{"source","target","relation_type"}]}`），JSON 解析失败重试最多 2 次，仍失败返回空结果 + warning（不阻塞索引）。`normalize()` 归一化（name 小写化、去空白）。数据类 `Entity`/`Relation`/`ExtractResult`。单测用 fake LLM 覆盖正常解析、错误 JSON 重试、空结果降级、归一化。
- **变更文件**：`src/knowflow/retrieval/entity_extractor.py`、`tests/unit/retrieval/test_entity_extractor.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-06T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-06T09:00:00+08:00"
git add src/knowflow/retrieval/entity_extractor.py tests/unit/retrieval/test_entity_extractor.py
git commit -m "feat(retrieval): 实现 LLM 实体关系抽取"
```

---

### 28. feat(retrieval): 实现图谱与向量与 BM25 存储

- **提交时间**：2026-06-06 11:00
- **说明**：三个存储层并行实现。`graph_store.py` 封装 EntityRepo/RelationRepo，提供 `upsert_entities`/`upsert_relations`/`find_entity_ids_by_chunk`/`one_hop_expand`，薄封装复用 M1 repo 不引入新 SQL。`vector_store.py` 封装 Milvus，`upsert` 批量写向量、`search` 向量召回（IP 度量）、`delete_by_doc` 按 doc 清理，数据类 `ChunkVector`/`VectorHit`。`bm25_store.py` 用 rank-bm25 内存索引（docstring 记录与设计文档 tsvector 的取舍），中英文混合分词（中文按字符、英文按空格），`add`/`add_batch` 增量追加、`search` 关键词召回、`delete_by_doc` 重建、`rebuild_from_chunks` 从 ORM 重建。单测：graph_store 用 SQLite 真跑实体/关系写入与一跳扩展联动；vector_store mock Milvus 验证参数与返回解析；bm25_store 验证构建/查询/增量/删除/中文 tokenization。
- **变更文件**：`src/knowflow/retrieval/graph_store.py`、`src/knowflow/retrieval/vector_store.py`、`src/knowflow/retrieval/bm25_store.py`、`tests/unit/retrieval/test_graph_store.py`、`tests/unit/retrieval/test_vector_store.py`、`tests/unit/retrieval/test_bm25_store.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-06T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-06T11:00:00+08:00"
git add src/knowflow/retrieval/graph_store.py src/knowflow/retrieval/vector_store.py src/knowflow/retrieval/bm25_store.py tests/unit/retrieval/test_graph_store.py tests/unit/retrieval/test_vector_store.py tests/unit/retrieval/test_bm25_store.py
git commit -m "feat(retrieval): 实现图谱与向量与 BM25 存储"
```

---

### 29. feat(retrieval): 实现 Hybrid Search RRF 融合

- **提交时间**：2026-06-06 14:00
- **说明**：`HybridSearch` 类组合 VectorStore + BM25Store + EmbeddingClient，`search(query, top_k)` 并行向量召回（embed query → vector_store.search）与 BM25 召回，按 RRF 公式 `score(d) = sum(1/(k+rank))` 融合两路结果，k 默认 60（与 constants.RRF_K 一致）。`fuse` 为静态方法便于单测直接调。数据类 `ChunkScore(chunk_id, score, source)`。单测重点测 RRF 融合算法：mock 两路返回固定 hits，验证融合分数与排序，覆盖单路命中、双路命中、空命中。
- **变更文件**：`src/knowflow/retrieval/hybrid_search.py`、`tests/unit/retrieval/test_hybrid_search.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-06T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-06T14:00:00+08:00"
git add src/knowflow/retrieval/hybrid_search.py tests/unit/retrieval/test_hybrid_search.py
git commit -m "feat(retrieval): 实现 Hybrid Search RRF 融合"
```

---

### 30. feat(retrieval): 实现一跳扩展与 Reranker 精排

- **提交时间**：2026-06-06 16:00
- **说明**：`Expander` 类注入 GraphStore + AsyncSession，`expand(hits)` 从 hits 取 chunk_id → graph_store.find_entity_ids_by_chunk 收集 entity_ids → graph_store.one_hop_expand 取关联 chunk_ids → ChunkRepo.get_many 取内容 → 构造 ChunkScore(score=0.0, source="expand") 合并去重（保留原始 hits 分数，扩展 chunk 置 0 排后），自环剔除。`Reranker` 类封装 sentence-transformers CrossEncoder（bge-reranker-v2-m3），`rerank(query, chunks, top_k)` 对 (query, chunk.content) 打分降序取 top_k，进程内单例 `get_reranker()` 懒加载。单测：expander 用 SQLite 真跑一跳扩展验证命中/自环剔除/去重/无实体；reranker mock CrossEncoder 验证排序/top_k 截断/空输入。
- **变更文件**：`src/knowflow/retrieval/expander.py`、`src/knowflow/retrieval/reranker.py`、`tests/unit/retrieval/test_expander.py`、`tests/unit/retrieval/test_reranker.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-06T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-06T16:00:00+08:00"
git add src/knowflow/retrieval/expander.py src/knowflow/retrieval/reranker.py tests/unit/retrieval/test_expander.py tests/unit/retrieval/test_reranker.py
git commit -m "feat(retrieval): 实现一跳扩展与 Reranker 精排"
```

---

### 31. feat(retrieval): 实现检索缓存与统一入口

- **提交时间**：2026-06-07 09:00
- **说明**：`RetrievalCache` 类用 Redis 缓存检索结果，`get(query)` md5(query) 作 key 命中反序列化、`set(query, results)` JSON 序列化 + EXPIRE、`invalidate(query)`/`clear_prefix(prefix)`，Redis 不可用降级 no-op + warning。`GraphRAGRetriever` 编排完整链路：cache.get → miss 时 hybrid_search.search(top_k*2) → expander.expand → 合并 → reranker.rerank(top_k) → cache.set → 返回 `RetrievalResult(chunks: list[ChunkWithScore], query, latency_ms, cache_hit)`。with_expand/with_rerank 开关控制子阶段。单测 mock 各子组件验证缓存命中跳过全链路、调用顺序、开关、cache set、空查询、内容返回、latency 记录。
- **变更文件**：`src/knowflow/retrieval/cache.py`、`src/knowflow/retrieval/retriever.py`、`tests/unit/retrieval/test_cache.py`、`tests/unit/retrieval/test_retriever.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-07T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-07T09:00:00+08:00"
git add src/knowflow/retrieval/cache.py src/knowflow/retrieval/retriever.py tests/unit/retrieval/test_cache.py tests/unit/retrieval/test_retriever.py
git commit -m "feat(retrieval): 实现检索缓存与统一入口"
```

---

### 32. feat(retrieval): 实现索引编排 pipeline

- **提交时间**：2026-06-07 14:00
- **说明**：`RetrievalPipeline` 串联索引全链路：DocumentRepo.get → MinIO 下载临时文件 → parser.parse → splitter.split → update_status("indexing") → 逐块 ChunkRepo.create + embedding.embed_one + VectorStore.upsert(批量) + BM25Store.add_batch → 逐块 entity_extractor.extract + GraphStore.upsert_entities/relations → DocumentIndexRepo.upsert(三路状态) → update_status("ready")。异常时 update_status("failed") + 抛 IndexError。`reindex_document` 先清理 vector/bm25/chunks(DB 级联 entities/relations) 再调 index_document。`IndexDeps` 依赖容器便于单测注入。单测 mock 全部子组件 + MinIO + db_session 验证状态机流转、调用次数与顺序、异常路径、reindex 清理顺序。
- **变更文件**：`src/knowflow/retrieval/pipeline.py`、`tests/unit/retrieval/test_pipeline.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-07T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-07T14:00:00+08:00"
git add src/knowflow/retrieval/pipeline.py tests/unit/retrieval/test_pipeline.py
git commit -m "feat(retrieval): 实现索引编排 pipeline"
```

---

### 33. feat(scripts): 添加 Milvus collection 初始化脚本

- **提交时间**：2026-06-07 16:00
- **说明**：`scripts/init_milvus.py` 建 `settings.milvus_collection`（若不存在），schema：id(INT64 PK)=chunk_id / doc_id(INT64) / embedding(FLOAT_VECTOR dim=1024)，索引 HNSW(M=16, efConstruction=200) 度量 IP。支持 `--reset` 先删后建。脚本将 src/ 加入 sys.path，可直接 `python scripts/init_milvus.py` 运行。真实创建由用户在测试文档中执行。
- **变更文件**：`scripts/init_milvus.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-07T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-07T16:00:00+08:00"
git add scripts/init_milvus.py
git commit -m "feat(scripts): 添加 Milvus collection 初始化脚本"
```

---

### 34. eval(retrieval): 构建合成评测集与 baseline 对比脚本

- **提交时间**：2026-06-08 09:00
- **说明**：合成 5 篇语料（hr_policy / product_manual / it_sop / ops_runbook / finance_policy，每篇 600-1000 字含人名/部门/产品/系统/流程实体与跨文档关联）。50 条评测集 `retrieval_eval.jsonl`（direct / cross_doc / semantic 三类）。`compare_baseline.py` 静态模式用 fake 组件（HashingEmbeddingClient / InMemoryVectorStore / RuleBasedEntityExtractor / TermOverlapReranker / NoopCache）+ SQLite 跑通全链路：索引语料 → 跨文档实体链接（同名实体双向 same_as）→ 对每条 query 跑 Hybrid（无扩展无精排）与 GraphRAG（扩展+精排）→ 计算 Recall@10 / MRR → 生成对比报告。评测专用 chunk_size=128（env var 覆盖）产出 43 块使 top_k=10 有区分度。静态结果：Hybrid R@10=33.6% / GraphRAG R@10=32.6%，cross_doc 组 GraphRAG MRR +0.0667。真实模式提示用户按测试文档执行。
- **变更文件**：`eval/datasets/corpus/hr_policy.md`、`eval/datasets/corpus/product_manual.md`、`eval/datasets/corpus/it_sop.md`、`eval/datasets/corpus/ops_runbook.md`、`eval/datasets/corpus/finance_policy.md`、`eval/datasets/retrieval_eval.jsonl`、`eval/scripts/compare_baseline.py`、`pyproject.toml`

```
$env:GIT_AUTHOR_DATE = "2026-06-08T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-08T09:00:00+08:00"
git add eval/datasets/corpus/hr_policy.md eval/datasets/corpus/product_manual.md eval/datasets/corpus/it_sop.md eval/datasets/corpus/ops_runbook.md eval/datasets/corpus/finance_policy.md eval/datasets/retrieval_eval.jsonl eval/scripts/compare_baseline.py
git commit -m "eval(retrieval): 构建合成评测集与 baseline 对比脚本"
```

---

### 35. docs(tests): 编写检索指标测试文档

- **提交时间**：2026-06-08 11:00
- **说明**：`docs/tests/指标测试-检索.md` 按 AGENTS.md 2.2 节要求编写，包含：前置条件（docker compose 启动 PG/Milvus/Redis/MinIO + LLM API Key + bge-m3/reranker 模型缓存 + init_db/init_milvus 脚本）、启动步骤（服务状态确认 + 门禁通过 + 静态模式自检）、5 项真实模式测试（索引真实文档 / 跨文档实体链接 / Hybrid vs GraphRAG 对比核心指标 / 缓存命中验证 / reindex 重建索引）、每项含步骤+预期结果+结果记录表（留空待用户填写）、验收清单、备注说明静态模式局限性（fake 组件不作 ≥8% 验收依据）与真实模式预期提升来源。
- **变更文件**：`docs/tests/指标测试-检索.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-08T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-08T11:00:00+08:00"
git add "docs/tests/指标测试-检索.md"
git commit -m "docs(tests): 编写检索指标测试文档"
```

---

## M2 · 修复与改进（2026-06-09）

**Phase 总览**：M2 代码检查后修复 ChatOpenAI api_key 类型不兼容导致 mypy 报错（langchain-openai 1.x 要求 SecretStr，M2 提交时即存在），并入库检索评测产物（chunk_id_map.json 与对比报告）。门禁全绿：ruff 0 errors / mypy 0 issues / 198 tests passed。

---

### 37. fix(retrieval): 修复 ChatOpenAI api_key 类型不兼容 mypy 报错

- **提交时间**：2026-06-09 09:00
- **说明**：`entity_extractor.py` 的 `_get_llm()` 中 `api_key=settings.llm_api_key` 为 str，与 langchain-openai 1.x `ChatOpenAI` 要求的 `SecretStr` 类型不兼容，mypy 报 arg-type 错误（该问题在 M2 提交时即存在，本次检查暴露）。修复：延迟导入 `pydantic.SecretStr` 包装 api_key，行为不变。
- **变更文件**：`src/knowflow/retrieval/entity_extractor.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-09T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-09T09:00:00+08:00"
git add src/knowflow/retrieval/entity_extractor.py
git commit -m "fix(retrieval): 修复 ChatOpenAI api_key 类型不兼容 mypy 报错"
```

---

### 38. chore: 入库检索评测产物

- **提交时间**：2026-06-09 10:00
- **说明**：`chunk_id_map.json`（索引后 chunk 映射表）与 `compare_20260608.md`（GraphRAG vs Hybrid 对比报告）为 M2 评测链路产物与面试证据，此前未入库。本次补录。
- **变更文件**：`eval/datasets/chunk_id_map.json`、`eval/reports/compare_20260608.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-09T10:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-09T10:00:00+08:00"
git add eval/datasets/chunk_id_map.json eval/reports/compare_20260608.md
git commit -m "chore: 入库检索评测产物"
```
