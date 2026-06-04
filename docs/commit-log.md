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
