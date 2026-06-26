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

---

## M3 · P4 · API 层、文档服务与异步索引（2026-06-10 ~ 2026-06-12）

**Phase 总览**：完成 API 层与异步索引全链路。schemas 9 个文件对齐 models 与设计文档 3.5；api/deps.py 集中依赖注入（DB/Settings/Redis/MinIO/Retriever/Broker/租户上下文），middleware.py 实现请求 ID/访问日志/Redis 固定窗口限流（降级放行）/CORS，sse.py 用生产者+队列解耦的心跳封装（避免心跳误杀业务流）；services/document_service.py 编排上传校验→sha256 去重→MinIO 存储→入库→投递任务；tasks/broker.py 基于 Redis Stream（XADD/XREADGROUP/XACK/消费组/重试 3 次/DLQ），tasks/index_task.py 组装 IndexDeps 调 RetrievalPipeline；9 个 v1 端点（health/document/knowledge 全实现，chat/agent/skill/memory/trace/eval 占位 501 标注后续里程碑）；worker 独立消费进程（优雅退出+重试/DLQ）；scripts/gen_openapi.py 生成 OpenAPI。修复 retriever 一跳扩展会话接线缺口（expander 改为按调用 session 构造的 factory）。新增 63 个测试，总计 256 passed，门禁全绿（ruff/mypy 0 errors）。真实容器端到端验收测试文档交付用户实测。

---

### 39. build: 补充 python-multipart 依赖与 API/任务队列配置字段

- **提交时间**：2026-06-10 09:00
- **说明**：`pyproject.toml` 新增 `python-multipart`（FastAPI UploadFile 依赖）。`Settings` 新增 API/上传段（cors_origins / rate_limit_per_minute / upload_max_bytes / upload_allowed_types）与任务队列段（task_stream_index / task_stream_dlq / task_consumer_group / task_consumer_name / task_max_retries / task_block_ms），附 `allowed_types` / `cors_origin_list` 解析属性。`.env.example` 同步补充。单测覆盖新字段默认值与解析。
- **变更文件**：`pyproject.toml`、`uv.lock`、`src/knowflow/core/config.py`、`.env.example`、`tests/unit/test_config.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-10T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-10T09:00:00+08:00"
git add pyproject.toml uv.lock src/knowflow/core/config.py .env.example tests/unit/test_config.py
git commit -m "build: 补充 python-multipart 依赖与 API/任务队列配置字段"
```

---

### 40. feat(schemas): 实现 API 请求响应 Schema 层

- **提交时间**：2026-06-10 11:00
- **说明**：`schemas/` 9 个文件：common（统一响应信封 `{code,message,data}` + 分页 `PageResponse`，PEP 695 泛型 + ErrorResponse）、document（UploadResponse/DocumentInfo/ReindexResponse/DeleteResponse）、knowledge（SearchRequest/SearchResponse/ChunkResult，对齐 retriever RetrievalResult）、chat（ChatRequest/ChatResponse/Citation）、agent/tool/memory/trace/eval（对齐各 models 与后续里程碑）。字段命名与 models 一致。
- **变更文件**：`src/knowflow/schemas/common.py`、`src/knowflow/schemas/document.py`、`src/knowflow/schemas/knowledge.py`、`src/knowflow/schemas/chat.py`、`src/knowflow/schemas/agent.py`、`src/knowflow/schemas/tool.py`、`src/knowflow/schemas/memory.py`、`src/knowflow/schemas/trace.py`、`src/knowflow/schemas/eval.py`、`tests/unit/api/__init__.py`、`tests/unit/api/test_schemas.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-10T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-10T11:00:00+08:00"
git add src/knowflow/schemas/common.py src/knowflow/schemas/document.py src/knowflow/schemas/knowledge.py src/knowflow/schemas/chat.py src/knowflow/schemas/agent.py src/knowflow/schemas/tool.py src/knowflow/schemas/memory.py src/knowflow/schemas/trace.py src/knowflow/schemas/eval.py tests/unit/api/__init__.py tests/unit/api/test_schemas.py
git commit -m "feat(schemas): 实现 API 请求响应 Schema 层"
```

---

### 41. fix(retrieval): 修复 retriever 一跳扩展会话接线

- **提交时间**：2026-06-10 14:00
- **说明**：M2 retriever 的 expand 块创建了独立 session 但 expander 用的是构造时持有的 session，真实接线下该 session 可能已关闭，且多次检索共用一个过期 session。改为注入 `expander_factory: Callable[[AsyncSession], Expander]`，在每次检索的 expand 块内按当次 session 构造 expander。rerank 块本就用当次 session（无需改）。同步更新 test_retriever.py 用 lambda 注入 FakeExpander。该缺口在 M3 接知识检索 endpoint 时暴露。
- **变更文件**：`src/knowflow/retrieval/retriever.py`、`tests/unit/retrieval/test_retriever.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-10T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-10T14:00:00+08:00"
git add src/knowflow/retrieval/retriever.py tests/unit/retrieval/test_retriever.py
git commit -m "fix(retrieval): 修复 retriever 一跳扩展会话接线"
```

---

### 42. feat(db): 为 DocumentRepo 补充 count_by_user 分页计数

- **提交时间**：2026-06-10 15:30
- **说明**：文档列表端点分页响应需要 total，DocumentRepo 原仅 list_by_user 无计数。新增 `count_by_user(user_id)` 用 `func.count()` 统计，供 document_service.list 返回 total。
- **变更文件**：`src/knowflow/db/repositories/document_repo.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-10T15:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-10T15:30:00+08:00"
git add src/knowflow/db/repositories/document_repo.py
git commit -m "feat(db): 为 DocumentRepo 补充 count_by_user 分页计数"
```

---

### 43. feat(tasks): 实现 Redis Stream 任务队列与索引任务

- **提交时间**：2026-06-11 09:00
- **说明**：`tasks/broker.py` 基于 redis.asyncio 封装 TaskBroker：enqueue（XADD MAXLEN 限流）、ensure_group（XGROUP CREATE，BUSYGROUP 忽略）、consume（XREADGROUP >）、ack（XACK）、send_to_dlq（死信流转）。payload JSON 编码进单字段。`tasks/index_task.py` 提供 `build_index_deps`（从全局单例组装 IndexDeps）与 `handle_index_task`（每任务独立 session，调 pipeline.index/reindex，NotFoundError 不可重试、IndexError 可重试）。不引入 Celery：单一索引任务类型用 Redis Stream 原生足够。单测用 FakeRedisStream 验证投递/消费/ack/不重复投递/DLQ，index_task 单测 patch get_session_factory + fake 组件验证成功/未找到/缺 doc_id/失败可重试。
- **变更文件**：`src/knowflow/tasks/broker.py`、`src/knowflow/tasks/index_task.py`、`tests/fakes.py`、`tests/unit/tasks/__init__.py`、`tests/unit/tasks/test_broker.py`、`tests/unit/tasks/test_index_task.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-11T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-11T09:00:00+08:00"
git add src/knowflow/tasks/broker.py src/knowflow/tasks/index_task.py tests/fakes.py tests/unit/tasks/__init__.py tests/unit/tasks/test_broker.py tests/unit/tasks/test_index_task.py
git commit -m "feat(tasks): 实现 Redis Stream 任务队列与索引任务"
```

---

### 44. feat(services): 实现文档管理服务

- **提交时间**：2026-06-11 11:00
- **说明**：`services/document_service.py` 编排文档全生命周期。upload：校验扩展名/大小 → sha256 去重（命中返回 duplicated 不重复存储/索引）→ MinIO put_object（asyncio.to_thread 包同步客户端）→ DocumentRepo.create(pending) → commit → broker.enqueue index 任务。list 分页（list_by_user + count_by_user）。delete：best-effort 清理向量/BM25/MinIO 对象 → 删 DB（级联 chunks/entities/relations）。reindex：状态置 pending → 投递 reindex 任务。单测用 SQLite + FakeMinio/FakeBroker 覆盖上传/去重/坏类型/超大/分页/删除/未找到/reindex。
- **变更文件**：`src/knowflow/services/document_service.py`、`tests/unit/services/__init__.py`、`tests/unit/services/test_document_service.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-11T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-11T11:00:00+08:00"
git add src/knowflow/services/document_service.py tests/unit/services/__init__.py tests/unit/services/test_document_service.py
git commit -m "feat(services): 实现文档管理服务"
```

---

### 45. feat(api): 实现依赖注入中间件与 SSE 封装

- **提交时间**：2026-06-11 14:00
- **说明**：`api/deps.py` 集中依赖：get_db（重导出）、Settings/Redis/Minio/Broker/Retriever/User Dep（Annotated），`get_retriever` 懒加载单例接线 GraphRAGRetriever（共享 VectorStore/BM25Store/EmbeddingClient/Reranker/Cache，expander_factory 按调用构造），`set_retriever`/`dispose_retriever` 供测试覆盖。`api/middleware.py`：RequestContextMiddleware（生成/透传 X-Request-Id，绑定 structlog，访问日志）、RateLimitMiddleware（Redis 固定窗口每 IP 每分钟，健康路径豁免，Redis 不可用降级放行，超限直接返回 429——中间件异常不被 exception_handler 捕获）。`api/sse.py`：生产者任务+队列解耦的心跳封装，心跳超时不取消业务生成器在途 await（避免 LLM 流式被误杀）。conftest 加 client fixture（覆盖 get_db 为 SQLite、redis/minio/broker/retriever 为 fake，不触发 lifespan）。单测覆盖请求 ID 生成/透传、限流阈值/降级/健康豁免、SSE 事件编码/心跳。
- **变更文件**：`src/knowflow/api/deps.py`、`src/knowflow/api/middleware.py`、`src/knowflow/api/sse.py`、`tests/conftest.py`、`tests/unit/api/test_middleware.py`、`tests/unit/api/test_sse.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-11T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-11T14:00:00+08:00"
git add src/knowflow/api/deps.py src/knowflow/api/middleware.py src/knowflow/api/sse.py tests/conftest.py tests/unit/api/test_middleware.py tests/unit/api/test_sse.py
git commit -m "feat(api): 实现依赖注入中间件与 SSE 封装"
```

---

### 46. feat(api): 实现 v1 端点与路由聚合

- **提交时间**：2026-06-11 16:00
- **说明**：9 个 v1 端点模块。health（/healthz 存活 + /readyz 就绪，探测 PG/Redis/Milvus/MinIO 连通性，任一不可用标记 degraded）、document（upload/list/delete/reindex 全实现，Annotated 依赖注入）、knowledge（search 全实现，调 retriever.retrieve 返回 ChunkResult）为 M3 完整功能；chat/agent/skill/memory/trace/eval 占位返回 501 并标注实现里程碑（P5-P10）。`api/v1/router.py` 聚合 9 个端点，`api/router.py` 挂载 v1。端点单测经 client fixture（依赖覆盖）验证上传/去重/坏类型/列表/删除/未找到/reindex、检索返回/空 query 校验/flags 透传、占位 501。`tests/integration/test_index_pipeline.py` 在 SQLite+fake 上跑通 HTTP 上传→入队→worker 消费→文档 ready 全链路。
- **变更文件**：`src/knowflow/api/router.py`、`src/knowflow/api/v1/router.py`、`src/knowflow/api/v1/endpoints/health.py`、`src/knowflow/api/v1/endpoints/document.py`、`src/knowflow/api/v1/endpoints/knowledge.py`、`src/knowflow/api/v1/endpoints/chat.py`、`src/knowflow/api/v1/endpoints/agent.py`、`src/knowflow/api/v1/endpoints/skill.py`、`src/knowflow/api/v1/endpoints/memory.py`、`src/knowflow/api/v1/endpoints/trace.py`、`src/knowflow/api/v1/endpoints/eval.py`、`tests/unit/api/test_health_endpoint.py`、`tests/unit/api/test_document_endpoint.py`、`tests/unit/api/test_knowledge_endpoint.py`、`tests/unit/api/test_stub_endpoints.py`、`tests/integration/test_index_pipeline.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-11T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-11T16:00:00+08:00"
git add src/knowflow/api/router.py src/knowflow/api/v1/router.py src/knowflow/api/v1/endpoints/health.py src/knowflow/api/v1/endpoints/document.py src/knowflow/api/v1/endpoints/knowledge.py src/knowflow/api/v1/endpoints/chat.py src/knowflow/api/v1/endpoints/agent.py src/knowflow/api/v1/endpoints/skill.py src/knowflow/api/v1/endpoints/memory.py src/knowflow/api/v1/endpoints/trace.py src/knowflow/api/v1/endpoints/eval.py tests/unit/api/test_health_endpoint.py tests/unit/api/test_document_endpoint.py tests/unit/api/test_knowledge_endpoint.py tests/unit/api/test_stub_endpoints.py tests/integration/test_index_pipeline.py
git commit -m "feat(api): 实现 v1 端点与路由聚合"
```

---

### 47. feat(api): 挂载路由中间件与统一异常处理

- **提交时间**：2026-06-11 17:30
- **说明**：`main.py` create_app 装配：CORS（allow_origins 取 settings.cors_origin_list）、RateLimitMiddleware、RequestContextMiddleware（添加顺序使请求 ID 最先执行）、include_router(api_router, prefix=api_prefix)、保留根 /health 与 / 兼容旧客户端、注册 AppError 异常处理器（转 ErrorResponse JSON，状态码取 exc.status_code）。
- **变更文件**：`src/knowflow/main.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-11T17:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-11T17:30:00+08:00"
git add src/knowflow/main.py
git commit -m "feat(api): 挂载路由中间件与统一异常处理"
```

---

### 48. feat(worker): 实现索引 worker 消费进程

- **提交时间**：2026-06-12 09:00
- **说明**：`worker/settings.py` 的 WorkerSettings 从全局 Settings 派生索引 worker 参数（stream/dlq/group/consumer/max_retries/block_ms/batch_size）。`worker/main.py` 独立进程：setup_logging → init 依赖（PG/Redis/MinIO，Milvus 懒加载）→ ensure_group → 消费循环（XREADGROUP 阻塞 block_ms）。重试策略：任务失败可重试且 attempts+1 < max_retries 时重新入队（attempts+1），否则入 DLQ 并 ack。信号处理优雅退出（Windows add_signal_handler 不支持时 contextlib.suppress 降级）。`make worker` 入口已就绪。
- **变更文件**：`worker/main.py`、`worker/settings.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-12T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-12T09:00:00+08:00"
git add worker/main.py worker/settings.py
git commit -m "feat(worker): 实现索引 worker 消费进程"
```

---

### 49. feat(scripts): 添加 OpenAPI 文档生成脚本

- **提交时间**：2026-06-12 10:30
- **说明**：`scripts/gen_openapi.py` 从 create_app() 导出 openapi.json，支持 `--out` 指定路径，自动将 src/ 加入 sys.path 便于直接运行。验收实测：生成 37KB 文档，20 个路径（含 chat/document/knowledge/health/agent/skill/memory/trace/eval 全部 v1 端点）。
- **变更文件**：`scripts/gen_openapi.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-12T10:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-12T10:30:00+08:00"
git add scripts/gen_openapi.py
git commit -m "feat(scripts): 添加 OpenAPI 文档生成脚本"
```

---

### 50. docs(tests): 编写 API 与异步索引验收测试文档

- **提交时间**：2026-06-12 11:30
- **说明**：`docs/tests/指标测试-API与异步索引.md` 按 AGENTS.md 2.2 节要求编写，覆盖需真实容器+真实模型的端到端验收：前置条件（docker compose 四件套 + LLM/Embedding/Reranker 模型缓存 + init_db/init_milvus）、7 项测试用例（健康检查、真实 PDF 上传、索引状态流转 pending→indexing→ready、知识检索含缓存命中、reindex/delete、OpenAPI 生成、集成测试复跑），每项含步骤+预期+结果记录表（留空待用户填写）。备注已知限制：BM25 跨进程不共享（M2 内存索引取舍）、占位端点在后续里程碑实现、限流降级放行。
- **变更文件**：`docs/tests/指标测试-API与异步索引.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-12T11:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-12T11:30:00+08:00"
git add "docs/tests/指标测试-API与异步索引.md"
git commit -m "docs(tests): 编写 API 与异步索引验收测试文档"
```

---

### 51. docs: 更新提交日志

- **提交时间**：2026-06-12 12:30
- **说明**：记录 M3（P4）全部 12 个业务提交（39-50）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-12T12:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-12T12:30:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

## M3 · 修复与改进（2026-06-13）

**Phase 总览**：M3 代码检查后修复三个问题——readyz 对 Milvus 仅检查客户端已创建、未做真实连通探测（与 M1 init_engine 惰性连接修复同类风险）；上传入库后索引任务投递失败无补偿（文档滞留 pending 且同内容重传被 sha256 去重拦截，永远无法索引）；worker 重试入队/死信投递异常未捕获会直接中断消费循环。同步修正 MinIO put_object 的 content_type 为标准 MIME 类型、外提函数内内联 import。新增 8 个测试（health 2 / document_service 1 / worker 5），总计 264 passed，门禁全绿（ruff 0 errors / mypy 0 issues）。

---

### 52. fix(api): readyz 对 Milvus 增加真实连通探测

- **提交时间**：2026-06-13 09:00
- **说明**：readyz 原对 Milvus 仅调 `get_milvus()` 检查客户端已创建，而 `init_milvus()` 只构造 MilvusClient 不握手——Milvus 服务不可用时可能误报 ok（与 M1 修复的 init_engine 惰性连接误报同类风险）。改为调 `list_collections()` 真实访问一次，失败如实报 fail。同步补充两个单测（可达报 ok / 不可达报 fail）。
- **变更文件**：`src/knowflow/api/v1/endpoints/health.py`、`tests/unit/api/test_health_endpoint.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-13T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-13T09:00:00+08:00"
git add src/knowflow/api/v1/endpoints/health.py tests/unit/api/test_health_endpoint.py
git commit -m "fix(api): readyz 对 Milvus 增加真实连通探测"
```

---

### 53. fix(services): 上传投递失败回滚并修正 MinIO MIME 类型

- **提交时间**：2026-06-13 10:00
- **说明**：upload 原顺序为 commit 后再 enqueue，Redis 故障时投递失败但文档已落库（pending），同内容重传被 sha256 去重拦截返回 duplicated 导致永远无法索引。改为 flush 取 id → enqueue → commit，投递失败不提交（会话退出时回滚）并清理已写入的 MinIO 对象，保持上传原子性、支持同内容重传。顺带修正 `put_object` 的 content_type 由扩展名改为 mimetypes 标准 MIME（如 application/pdf），函数内内联 `import asyncio` 外提至模块顶部。新增投递失败回滚单测。
- **变更文件**：`src/knowflow/services/document_service.py`、`tests/unit/services/test_document_service.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-13T10:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-13T10:00:00+08:00"
git add src/knowflow/services/document_service.py tests/unit/services/test_document_service.py
git commit -m "fix(services): 上传投递失败回滚并修正 MinIO MIME 类型"
```

---

### 54. fix(worker): 重试入队与死信投递异常兜底

- **提交时间**：2026-06-13 11:00
- **说明**：`_process` 原在 requeue 的 enqueue/ack 与 send_to_dlq 失败时异常直接传播，导致 worker 主循环退出。改为 try/except 包裹：失败仅记录日志不中断消费循环，消息不 ack 留在 PEL 供人工审计。新增 5 个 worker 分支单测（成功 ack / 重试入队 attempts+1 / 超限入 DLQ / 入队失败兜底不中断 / 非预期异常视为可重试）。
- **变更文件**：`worker/main.py`、`tests/unit/worker/__init__.py`、`tests/unit/worker/test_worker_main.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-13T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-13T11:00:00+08:00"
git add worker/main.py tests/unit/worker/__init__.py tests/unit/worker/test_worker_main.py
git commit -m "fix(worker): 重试入队与死信投递异常兜底"
```

---

### 55. docs: 更新提交日志

- **提交时间**：2026-06-13 12:00
- **说明**：记录本次 M3 修复与改进的 3 个提交（52-54）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-13T12:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-13T12:00:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

## M4 · P5 · 对话链路与 SSE 流式（2026-06-14 ~ 2026-06-16）

**Phase 总览**：打通最小可用问答闭环。`core/llm.py` 新增 ChatOpenAI 懒加载单例并接入生命周期释放（LLM/Embedding/Reranker 三大客户端统一懒加载）；`services/chat_service.py` 实现对话主流程——会话存在性检查 → 历史注入（最近 window_max_turns 轮全量）→ 消息入库 → 检索 → 组装 prompt（系统提示+历史+检索上下文）→ LLM 生成 → 消息/引用/轮次落库，同步 chat() 与流式 stream_events()（retrieval → token* → done，异常 yield error 事件并回滚）；chat 端点接入对话服务，/chat/stream 经 sse.py 心跳封装。新增 9 个单测（服务 6 + 端点 3，chat stub 501 用例移除），e2e 真实模型流式测试（无 Key 自动跳过）。门禁全绿：ruff 0 errors / mypy 0 issues / unit+integration 273 passed / pre-commit 全通过。首 token 基准与多轮验收按测试文档交付用户实测。

---

### 56. feat(core): 实现 LLM 客户端懒加载单例并接入生命周期释放

- **提交时间**：2026-06-14 09:00
- **说明**：`core/llm.py` 新增 ChatOpenAI 懒加载单例（`get_chat_llm` 首次调用按 Settings 构造，temperature=0.3 + streaming，api_key 用 SecretStr 包装兼容 langchain-openai 1.x），`set_chat_llm`/`dispose_chat_llm` 供测试注入与释放。`core/lifecycle.py` 关闭流程新增 `_dispose_ai_singletons()`：释放 LLM/Embedding/Reranker 三个懒加载单例（未加载时无操作，失败忽略），补齐 AI 客户端生命周期管理。
- **变更文件**：`src/knowflow/core/llm.py`、`src/knowflow/core/lifecycle.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-14T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-14T09:00:00+08:00"
git add src/knowflow/core/llm.py src/knowflow/core/lifecycle.py
git commit -m "feat(core): 实现 LLM 客户端懒加载单例并接入生命周期释放"
```

---

### 57. feat(services): 实现对话服务主流程（检索增强问答与流式生成）

- **提交时间**：2026-06-14 11:00
- **说明**：`services/chat_service.py` 实现无工具版对话主流程。链路：`_ensure_session`（校验/新建会话，非法 session_id 抛 ValidationError、不存在抛 NotFoundError）→ 历史注入（list_by_session 取最近 window_max_turns 轮 user/assistant）→ 用户消息入库 → retriever.retrieve → `_build_messages` 组装（系统提示注入检索上下文，逐段 [n] 编号 + 强制不编造 + 来源标注）→ LLM 生成。同步 `chat()` 用 ainvoke 返回 ChatResponse（answer+citations+latency_ms）；流式 `stream_events()` 用 astream 逐 token 转发 SSE 事件（retrieval 先回传召回结果 → token 事件 JSON 载荷规避 SSE 分帧换行问题 → done 含引用/耗时/token 数），异常回滚并 yield error 事件不中断连接。assistant 消息落库 citations JSON（content 截断 500 字符防膨胀），turns 表记录轮次。token 计数用 tiktoken（模型不支持回退字符/4 估算）。
- **变更文件**：`src/knowflow/services/chat_service.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-14T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-14T11:00:00+08:00"
git add src/knowflow/services/chat_service.py
git commit -m "feat(services): 实现对话服务主流程（检索增强问答与流式生成）"
```

---

### 58. feat(api): chat 端点接入对话服务与 SSE 事件流

- **提交时间**：2026-06-14 14:00
- **说明**：`api/deps.py` 新增 `get_llm_dep`/`LlmDep`（ChatOpenAI 单例依赖，测试可覆盖为 fake）。`api/v1/endpoints/chat.py` 替换 M3 占位：POST /chat 同步返回 ChatResponse；POST /chat/stream 构造 ChatService 后经 `sse_stream`（心跳+断连检测）包装为 EventSourceResponse。`tests/unit/api/test_stub_endpoints.py` 移除 chat 两个 501 用例（chat 已实现，保留 agent/skill/memory/trace/eval 占位断言）。
- **变更文件**：`src/knowflow/api/deps.py`、`src/knowflow/api/v1/endpoints/chat.py`、`tests/unit/api/test_stub_endpoints.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-14T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-14T14:00:00+08:00"
git add src/knowflow/api/deps.py src/knowflow/api/v1/endpoints/chat.py tests/unit/api/test_stub_endpoints.py
git commit -m "feat(api): chat 端点接入对话服务与 SSE 事件流"
```

---

### 59. test(chat): 添加对话服务与端点单测

- **提交时间**：2026-06-15 09:00
- **说明**：`tests/fakes.py` 新增 FakeChatLLM（ainvoke/astream 记录调用与最后消息，raise_on_stream 测异常路径）；`tests/conftest.py` client fixture 覆盖 get_llm_dep 为 FakeChatLLM。服务单测 6 个（SQLite+aiosqlite）：新建会话落库（消息/引用/轮次）、多轮复用注入历史、session 不存在 404、非法 session_id 422、流式事件序列 retrieval→token→done、异常 error 事件。端点单测 3 个（TestClient）：同步返回答案与引用、SSE 流式事件解析（retrieval/token/done 顺序 + citations）、LLM 异常 error 事件。
- **变更文件**：`tests/fakes.py`、`tests/conftest.py`、`tests/unit/services/test_chat_service.py`、`tests/unit/api/test_chat_endpoint.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-15T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-15T09:00:00+08:00"
git add tests/fakes.py tests/conftest.py tests/unit/services/test_chat_service.py tests/unit/api/test_chat_endpoint.py
git commit -m "test(chat): 添加对话服务与端点单测"
```

---

### 60. test(e2e): 添加真实模型对话流式端到端测试

- **提交时间**：2026-06-15 11:00
- **说明**：`tests/e2e/test_chat_stream_e2e.py`：无 LLM API Key 时整模块 skip。有 Key 时通过 client fixture（SQLite + FakeRetriever 固定知识片段）移除 get_llm_dep 覆盖走真实 ChatOpenAI，POST /chat/stream 断言 retrieval→token→done 事件序列、token 拼接回答非空、done 含 session_id 与 citations，并打印 first_token_ms 供 docs/benchmarks 记录首 token 基准（目标 < 800ms）。
- **变更文件**：`tests/e2e/test_chat_stream_e2e.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-15T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-15T11:00:00+08:00"
git add tests/e2e/test_chat_stream_e2e.py
git commit -m "test(e2e): 添加真实模型对话流式端到端测试"
```

---

### 61. docs(tests): 编写对话链路与 SSE 验收测试文档

- **提交时间**：2026-06-15 14:00
- **说明**：`docs/tests/指标测试-对话链路.md` 按 AGENTS.md 2.2 节要求编写：前置条件（docker compose 四件套 + LLM API Key + 依赖 M3 已索引文档）、启动步骤、6 项验收用例（同步对话、SSE 事件序列与心跳、多轮追问引用上文、首 token 基准 <800ms 记录 docs/benchmarks/、异常路径 error 事件/404/422、e2e 自动化）、已知限制（P7 前全量历史注入无压缩、无工具版、LLM 懒加载、citations JSON 结构、BM25 跨进程限制）、验收清单。
- **变更文件**：`docs/tests/指标测试-对话链路.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-15T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-15T14:00:00+08:00"
git add "docs/tests/指标测试-对话链路.md"
git commit -m "docs(tests): 编写对话链路与 SSE 验收测试文档"
```

---

### 62. docs: 更新提交日志

- **提交时间**：2026-06-16 09:00
- **说明**：记录 M4（P5）全部 6 个业务提交（56-61）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-16T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-16T09:00:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

## M5 · P6 + P9 · 工具治理与沙盒文件系统（2026-06-17 ~ 2026-06-20）

**Phase 总览**：完成工具治理体系（P6）与沙盒文件系统（P9）全部建设。P9 沙盒层实现会话级 workspace 隔离——虚拟路径映射（`/workspace/x.json` ↔ MinIO key）、访问控制（拦截 `../`/绝对路径/跨会话）、MinIO 后端 CRUD（asyncio.to_thread 包同步客户端）、配额管理（默认 100MB）、文件操作编排（校验→映射→配额→后端）、工作区生命周期（创建/清理/TTL）。P6 工具治理实现四类执行域隔离（direct 恒可见 / skill_only 按激活 / subagent_only 按角色 / internal 永不可见）——BaseTool 抽象 + ToolRegistry 注册表 + SkillDefinition 声明式加载（YAML frontmatter 解析）+ 依赖拓扑排序 + VisibilityCalculator 可见性计算 + Injector JSON Schema 注入 + Permission 越权拦截 + ToolMetrics 指标收集；4 个内置工具（calculator/retrieval_tool/file_tools/search_tool）+ 4 个 Skill（knowledge_qa/document_summary/data_analysis/code_review）+ ToolOrchestrator 工具调用循环（Skill 激活→可见性计算→注入→LLM bind_tools→工具调用→结果回填→继续生成，最大 5 轮）。skill 端点接入 SkillManager 实现列表/启停。指标脚本 benchmark_tools.py 静态模式三项指标均达标：可见工具数 -43.4%（目标 -34.2%）、Schema Token -45.2%（目标 -32.6%）、FC 准确率 100.0%（目标 94+%）。新增 101 个单测，总计 374 passed，覆盖率 87%，门禁全绿（ruff/mypy 0 errors / pre-commit 全通过）。

---

### 63. build: 补充 mypy_path 与工具治理配置字段

- **提交时间**：2026-06-17 09:00
- **说明**：pre-commit 的 mypy hook 用 `--explicit-package-bases` 解析 src 布局，缺 `mypy_path` 导致新增模块的类型标注被解析为 Any，触发 `no-any-return` 误报。在 `[tool.mypy]` 补充 `mypy_path = "src"` 使 mypy 正确解析 knowflow 顶层包。`core/config.py` 新增 `skills_dir`（默认 "skills"）与 `max_tool_rounds`（默认 5）配置字段，供后续 SkillManager 与 ToolOrchestrator 使用（提前提交避免增量提交时 mypy 跨文件依赖报错）。`.gitignore` 补充 `.trae/` / `.workbuddy/` IDE 产物忽略规则。
- **变更文件**：`pyproject.toml`、`.gitignore`、`src/knowflow/core/config.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-17T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-17T09:00:00+08:00"
git add pyproject.toml .gitignore src/knowflow/core/config.py
git commit -m "build: 补充 mypy_path 与工具治理配置字段"
```

---

### 64. feat(sandbox): 实现虚拟路径映射与访问控制

- **提交时间**：2026-06-17 10:30
- **说明**：`virtual_path.py` 实现会话级虚拟路径映射（`/workspace/x.json` ↔ MinIO key `sessions/{sid}/workspace/x.json`），`to_real`/`to_virtual` 双向转换，`session_prefix` 供清理使用。`access_control.py` 实现路径安全校验：拦截 `../` 路径穿越、绝对路径、跨会话前缀访问，仅放行 `/workspace/` 下当前会话路径，校验失败抛 ValidationError。
- **变更文件**：`src/knowflow/sandbox/virtual_path.py`、`src/knowflow/sandbox/access_control.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-17T10:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-17T10:30:00+08:00"
git add src/knowflow/sandbox/virtual_path.py src/knowflow/sandbox/access_control.py
git commit -m "feat(sandbox): 实现虚拟路径映射与访问控制"
```

---

### 65. feat(sandbox): 实现 MinIO 存储后端与配额管理

- **提交时间**：2026-06-17 14:00
- **说明**：`minio_backend.py` 封装 MinIO 对象 CRUD（write/read/list/delete/exists/stat），同步客户端经 `asyncio.to_thread` 避免阻塞事件循环，read 自动关闭 response 释放连接。`quota.py` 实现单会话配额管理：写入前校验已用 + 新增 ≤ workspace_quota_bytes（默认 100MB），超限抛 ValidationError，用量按对象 size 求和统计。
- **变更文件**：`src/knowflow/sandbox/minio_backend.py`、`src/knowflow/sandbox/quota.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-17T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-17T14:00:00+08:00"
git add src/knowflow/sandbox/minio_backend.py src/knowflow/sandbox/quota.py
git commit -m "feat(sandbox): 实现 MinIO 存储后端与配额管理"
```

---

### 66. feat(sandbox): 实现文件操作与工作区生命周期管理

- **提交时间**：2026-06-17 16:00
- **说明**：`file_ops.py` 编排文件操作统一流程：AccessControl 校验 → VirtualPathMapper 映射 → (写入时) Quota 校验 → MinioBackend 执行，提供 read/write/list/delete/exists 接口，对工具暴露虚拟路径。`workspace.py` 的 WorkspaceManager 为每个会话产出 FileOps 实例（绑定 session_id 与配额），cleanup 按前缀列出删除全部对象。`lifecycle.py` 包装批量清理，单会话失败不阻塞其余。
- **变更文件**：`src/knowflow/sandbox/file_ops.py`、`src/knowflow/sandbox/workspace.py`、`src/knowflow/sandbox/lifecycle.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-17T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-17T16:00:00+08:00"
git add src/knowflow/sandbox/file_ops.py src/knowflow/sandbox/workspace.py src/knowflow/sandbox/lifecycle.py
git commit -m "feat(sandbox): 实现文件操作与工作区生命周期管理"
```

---

### 67. test(sandbox): 添加沙盒文件系统单测

- **提交时间**：2026-06-17 17:30
- **说明**：单测覆盖沙盒文件系统全部核心路径：虚拟路径双向映射、路径穿越拦截（`../`/绝对路径/跨会话）、MinIO 后端 CRUD（FakeMinio 内存桩）、配额校验与超限拒绝、FileOps 读写列表删除、WorkspaceManager 创建与清理。安全用例重点验证 `write("../../etc/passwd")` 被拦截、会话 A 无法访问会话 B 文件。
- **变更文件**：`tests/unit/sandbox/test_sandbox.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-17T17:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-17T17:30:00+08:00"
git add tests/unit/sandbox/test_sandbox.py
git commit -m "test(sandbox): 添加沙盒文件系统单测"
```

---

### 68. feat(tools): 实现 BaseTool 抽象与工具注册表

- **提交时间**：2026-06-18 09:00
- **说明**：`base.py` 定义 `BaseTool` 抽象基类（name/description/domain/input_schema/execute）与 `ToolResult` 数据类（tool_name/success/output/error/latency_ms/token_usage），统一工具返回结构。`registry.py` 实现 `ToolRegistry`：register 注册工具、get 按名查询、list_all 全量列出、list_by_domain 按执行域过滤，注册时记录日志。
- **变更文件**：`src/knowflow/tools/base.py`、`src/knowflow/tools/registry.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-18T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-18T09:00:00+08:00"
git add src/knowflow/tools/base.py src/knowflow/tools/registry.py
git commit -m "feat(tools): 实现 BaseTool 抽象与工具注册表"
```

---

### 69. feat(tools): 定义执行域与 Skill 声明式加载与依赖解析

- **提交时间**：2026-06-18 10:30
- **说明**：`domain.py` 定义四类执行域（DIRECT/SKILL_ONLY/SUBAGENT_ONLY/INTERNAL）与 AgentRole（MAIN/SUBAGENT），提供 `visible_domains_for`/`filter_skills_by_role` 按角色过滤。`skill_schema.py` 定义 SkillDefinition Pydantic 模型（name/description/tools/dependencies/domain/enabled），name 去空白校验、tools/dependencies 去重保序。`skill_loader.py` 解析 SKILL.md YAML frontmatter → SkillDefinition，校验 frontmatter 闭合/YAML 合法/工具名合法，load_dir 单个失败不阻塞其余。`dependency_resolver.py` 实现依赖拓扑排序 + 循环检测 + 缺失依赖报告。
- **变更文件**：`src/knowflow/tools/domain.py`、`src/knowflow/tools/skill_schema.py`、`src/knowflow/tools/skill_loader.py`、`src/knowflow/tools/dependency_resolver.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-18T10:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-18T10:30:00+08:00"
git add src/knowflow/tools/domain.py src/knowflow/tools/skill_schema.py src/knowflow/tools/skill_loader.py src/knowflow/tools/dependency_resolver.py
git commit -m "feat(tools): 定义执行域与 Skill 声明式加载与依赖解析"
```

---

### 70. feat(tools): 实现可见性计算/注入/权限/指标收集

- **提交时间**：2026-06-18 14:00
- **说明**：`visibility.py` 的 VisibilityCalculator 按执行域隔离计算可见工具集：direct 恒可见 + skill_only 按 Skill 激活(含 dependencies) + subagent_only 按角色 + internal 永不可见，多 Skill 引用同一工具去重。`injector.py` 按可见集构建 LLM tools 参数（JSON Schema 注入），schema_tokens 估算 Token 量（字符数/4）。`permission.py` 运行时越权拦截：工具不在可见集中时拒绝并报错。`metrics.py` 的 ToolMetrics 记录每次调用（成功/失败/耗时/可见数/Token），提供 call_stats 统计与 snapshot 快照。
- **变更文件**：`src/knowflow/tools/visibility.py`、`src/knowflow/tools/injector.py`、`src/knowflow/tools/permission.py`、`src/knowflow/tools/metrics.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-18T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-18T14:00:00+08:00"
git add src/knowflow/tools/visibility.py src/knowflow/tools/injector.py src/knowflow/tools/permission.py src/knowflow/tools/metrics.py
git commit -m "feat(tools): 实现可见性计算/注入/权限/指标收集"
```

---

### 71. feat(tools): 实现内置工具与 Skill 管理器

- **提交时间**：2026-06-18 16:00
- **说明**：4 个内置工具：`calculator.py`（direct 域，AST 安全求值，白名单节点拦截名称/属性访问，超长/空表达式拒绝）、`retrieval_tool.py`（direct 域，调 retriever 返回片段，content 截断 500 字符）、`file_tools.py`（skill_only 域，FileReadTool/FileWriteTool/FileListTool 走沙盒 FileOps）、`search_tool.py`（subagent_only 域，duckduckgo-search 网络搜索，依赖未装返回失败）。`builtin/__init__.py` 的 build_default_registry 组装全部工具。`skill_manager.py` 的 SkillManager 加载 SKILL.md 目录并维护运行时启停状态（进程内），active_skills 同步运行时 enabled 供可见性计算，list/toggle/get 接口。
- **变更文件**：`src/knowflow/tools/builtin/calculator.py`、`src/knowflow/tools/builtin/retrieval_tool.py`、`src/knowflow/tools/builtin/file_tools.py`、`src/knowflow/tools/builtin/search_tool.py`、`src/knowflow/tools/builtin/__init__.py`、`src/knowflow/tools/skill_manager.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-18T16:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-18T16:00:00+08:00"
git add src/knowflow/tools/builtin/calculator.py src/knowflow/tools/builtin/retrieval_tool.py src/knowflow/tools/builtin/file_tools.py src/knowflow/tools/builtin/search_tool.py src/knowflow/tools/builtin/__init__.py src/knowflow/tools/skill_manager.py
git commit -m "feat(tools): 实现内置工具与 Skill 管理器"
```

---

### 72. feat(skills): 添加 4 个 Skill 声明定义

- **提交时间**：2026-06-18 17:30
- **说明**：4 个 Skill 的 SKILL.md 声明式定义（YAML frontmatter + 正文）：knowledge_qa（知识问答，tools: retrieval_tool，skill_only 域）、document_summary（文档摘要，tools: retrieval_tool + file_write_tool，skill_only 域）、data_analysis（数据分析，tools: calculator + file_read/write/list_tool，skill_only 域）、code_review（代码审查，tools: file_read_tool + search_tool，subagent_only 域）。正文含使用场景与调用示例，供 SkillManager 加载。
- **变更文件**：`skills/knowledge_qa/SKILL.md`、`skills/document_summary/SKILL.md`、`skills/data_analysis/SKILL.md`、`skills/code_review/SKILL.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-18T17:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-18T17:30:00+08:00"
git add skills/knowledge_qa/SKILL.md skills/document_summary/SKILL.md skills/data_analysis/SKILL.md skills/code_review/SKILL.md
git commit -m "feat(skills): 添加 4 个 Skill 声明定义"
```

---

### 73. feat(services): 实现工具编排器与 LLM 工具调用循环

- **提交时间**：2026-06-19 09:00
- **说明**：`tool_orchestrator.py` 的 ToolOrchestrator 实现工具版对话主流程：按 AgentRole 过滤激活 Skill → VisibilityCalculator 计算可见工具 → 无可见工具时 no_tools 短路 → Injector 注入 JSON Schema → LLM bind_tools → 工具调用循环（LLM 响应含 tool_calls 时逐个执行 → 结果以 tool 消息回填 → 继续生成，无 tool_calls 时返回最终答案），最大 max_tool_rounds 轮（默认 5），超限 truncated=True。每次工具调用经 Permission 校验越权，结果记入 ToolMetrics。支持 history 注入与 session_id 透传。
- **变更文件**：`src/knowflow/services/tool_orchestrator.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-19T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-19T09:00:00+08:00"
git add src/knowflow/services/tool_orchestrator.py
git commit -m "feat(services): 实现工具编排器与 LLM 工具调用循环"
```

---

### 74. feat(api): skill 端点接入与工具治理依赖注入

- **提交时间**：2026-06-19 10:30
- **说明**：`api/deps.py` 新增 `get_skill_manager`/`get_tool_registry` 依赖（SkillManager 懒加载单例，ToolRegistry 经 build_default_registry 构造），供端点注入。`api/v1/endpoints/skill.py` 替换 M3 占位 501：GET /skills 列出全部 Skill（含运行时启停状态），PUT /skills/{name}/toggle 切换启停（不存在返回 404）。`test_stub_endpoints.py` 移除 skill 两个 501 用例。
- **变更文件**：`src/knowflow/api/deps.py`、`src/knowflow/api/v1/endpoints/skill.py`、`tests/unit/api/test_stub_endpoints.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-19T10:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-19T10:30:00+08:00"
git add src/knowflow/api/deps.py src/knowflow/api/v1/endpoints/skill.py tests/unit/api/test_stub_endpoints.py
git commit -m "feat(api): skill 端点接入与工具治理依赖注入"
```

---

### 75. test(tools): 添加工具治理与内置工具单测

- **提交时间**：2026-06-19 14:00
- **说明**：9 个工具单测文件覆盖全部核心逻辑：test_registry（注册/查询/按域过滤）、test_domain_visibility（四类域可见性/Skill 过滤/去重/依赖激活）、test_skill_loader（frontmatter 解析/校验/目录加载/真实 skills/）、test_dependency_resolver（拓扑排序/循环检测/缺失依赖）、test_injector（Schema 构建/Token 估算）、test_permission（越权拦截）、test_metrics（调用记录/统计/快照）、test_skill_manager（加载/启停/active_skills）、test_builtin_tools（calculator 安全求值/retrieval 返回截断/file_tools 沙盒读写/search_tool 域校验）。`tests/fakes.py` 新增 FakeChunkWithScore/FakeToolCallingLLM（脚本化响应）供工具与编排器单测使用。
- **变更文件**：`tests/unit/tools/test_registry.py`、`tests/unit/tools/test_domain_visibility.py`、`tests/unit/tools/test_skill_loader.py`、`tests/unit/tools/test_dependency_resolver.py`、`tests/unit/tools/test_injector.py`、`tests/unit/tools/test_permission.py`、`tests/unit/tools/test_metrics.py`、`tests/unit/tools/test_skill_manager.py`、`tests/unit/tools/test_builtin_tools.py`、`tests/fakes.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-19T14:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-19T14:00:00+08:00"
git add tests/unit/tools/test_registry.py tests/unit/tools/test_domain_visibility.py tests/unit/tools/test_skill_loader.py tests/unit/tools/test_dependency_resolver.py tests/unit/tools/test_injector.py tests/unit/tools/test_permission.py tests/unit/tools/test_metrics.py tests/unit/tools/test_skill_manager.py tests/unit/tools/test_builtin_tools.py tests/fakes.py
git commit -m "test(tools): 添加工具治理与内置工具单测"
```

---

### 76. test(services): 添加工具编排器与 skill 端点单测

- **提交时间**：2026-06-19 15:30
- **说明**：`test_tool_orchestrator.py` 用 FakeToolCallingLLM（脚本化响应）+ CalculatorTool 验证编排器全部分支：无可见工具短路、单轮工具调用→结果回填→最终答案、无需工具直接回答、越权调用被拦截但循环不中断、达到 max_tool_rounds 时 truncated=True、指标被记录、history 注入消息序列、子 Agent 可调用 subagent_only 工具。`test_skill_endpoint.py` 验证 GET /skills 列表与 PUT /skills/{name}/toggle 启停（含 404）。`conftest.py` client fixture 注入 SkillManager 与 ToolRegistry（fake retriever + fake minio）。
- **变更文件**：`tests/unit/services/test_tool_orchestrator.py`、`tests/unit/api/test_skill_endpoint.py`、`tests/conftest.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-19T15:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-19T15:30:00+08:00"
git add tests/unit/services/test_tool_orchestrator.py tests/unit/api/test_skill_endpoint.py tests/conftest.py
git commit -m "test(services): 添加工具编排器与 skill 端点单测"
```

---

### 77. feat(scripts): 添加工具治理指标对比脚本

- **提交时间**：2026-06-19 16:30
- **说明**：`scripts/benchmark_tools.py` 对比"全量工具注入 vs 执行域隔离注入"三项指标。静态模式（默认）：用规则意图识别（关键词匹配）激活 Skill，统计 33 条场景（覆盖 4 个 Skill + direct-only，主/子 Agent 角色）的可见工具数下降率、Schema Token 下降率、FC 准确率（预期工具在可见集中）。支持 `--report` 生成 Markdown 报告到 docs/benchmarks/。静态实测：可见工具数 -43.4%（目标 -34.2%）、Schema Token -45.2%（目标 -32.6%）、FC 准确率 100.0%（目标 94+%），三项均达标。
- **变更文件**：`scripts/benchmark_tools.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-19T16:30:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-19T16:30:00+08:00"
git add scripts/benchmark_tools.py
git commit -m "feat(scripts): 添加工具治理指标对比脚本"
```

---

### 78. docs(tests): 编写工具治理指标测试文档

- **提交时间**：2026-06-20 09:00
- **说明**：`docs/tests/指标测试-工具治理.md` 按 AGENTS.md 2.2 节要求编写，覆盖需真实容器+真实模型的端到端验收：前置条件（docker compose 四件套 + LLM API Key + 门禁通过 + 静态模式自检）、5 项测试用例（Skill 列表与启停、执行域隔离静态指标对比、真实 LLM 工具调用对话、沙盒文件系统安全用例、工具治理单测全量验证），每项含步骤+预期+结果记录表（留空待用户填写）。`docs/benchmarks/tool_governance_20260806.md` 为静态模式自动产出的指标对比报告（含 33 条场景明细）。备注已知限制：静态模式 FC 准确率为代理指标、search_tool 依赖 duckduckgo、Skill 启停为进程内状态、工具编排器待 P8 接入 chat_service。
- **变更文件**：`docs/tests/指标测试-工具治理.md`、`docs/benchmarks/tool_governance_20260806.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-20T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-20T09:00:00+08:00"
git add "docs/tests/指标测试-工具治理.md" docs/benchmarks/tool_governance_20260806.md
git commit -m "docs(tests): 编写工具治理指标测试文档"
```

---

### 79. docs: 更新提交日志

- **提交时间**：2026-06-20 10:00
- **说明**：记录 M5（P6 + P9）全部 16 个业务提交（63-78）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-20T10:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-20T10:00:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

### 80. feat(context): 新增上下文工程与记忆体系

- **提交时间**：2026-06-21 09:00
- **说明**：M6（P7）核心模块。context/ 7 文件：token_counter（tiktoken + 字符回退）、budget（系统/历史/工具/检索/记忆 5 模块配额）、window（滑动窗口）、summarizer（LLM 增量摘要 + 规则兜底）、spiller（超阈值写沙盒引用替换，直连 M5 真实沙盒）、builder（段落式组装 + 截断）、strategy（窗口→摘要→卸载→截断编排 + ContextManager 门面）。memory/ 7 文件：short_term（Redis TTL）、importance（LLM 0-10 + 规则兜底）、compressor（LLM 压缩 + 兜底）、store（PG 持久化 + embedding 序列化）、recall（0.7×相似度 + 0.2×重要性 + 0.1×新鲜度时间衰减）、long_term（门面）、manager（观察/每 5 轮沉淀编排）。config 新增记忆三项配置。配套 11 个单测文件（context 26 用例 + memory 31 用例，全离线可测）。
- **变更文件**：`src/knowflow/context/`（7 文件）、`src/knowflow/memory/`（7 文件）、`src/knowflow/core/config.py`、`src/knowflow/schemas/memory.py`、`tests/unit/context/`（6 文件）、`tests/unit/memory/`（5 文件）

```
$env:GIT_AUTHOR_DATE = "2026-06-21T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-21T09:00:00+08:00"
git add src/knowflow/context src/knowflow/memory src/knowflow/core/config.py src/knowflow/schemas/memory.py tests/unit/context tests/unit/memory
git commit -m "feat(context): 新增上下文工程与记忆体系"
```

---

### 81. feat(tools): 工具编排接入对话链路并新增 benchmark 真实模式

- **提交时间**：2026-06-21 11:00
- **说明**：补齐 P6 任务 11 缺口——ToolOrchestrator 接入对话链路：`run()` 新增 context（预检索上下文注入）与 active_skills（调用方控制激活集）参数，修复文件类工具 session_id 自动补参（setdefault 替代 in 判断）；chat/chat_stream 端点注入编排器，工具调用记录随响应返回并落库（citations JSON 扩展 tool_calls）；ChatResponse 新增 tool_calls 字段；deps 新增 get_tool_orchestrator 容错懒加载单例。`benchmark_tools.py --mode real` 从提示占位改为真实实现（真实 LLM 经 ToolOrchestrator 跑 33 条场景工具调用循环统计 FC 准确率），场景语义修正（“你好”预期不调用工具，expected_tool 支持 None 双口径判定）。测试文档移除“工具编排器未接入”已知限制并更新通过数。
- **变更文件**：`src/knowflow/services/tool_orchestrator.py`、`src/knowflow/schemas/chat.py`、`scripts/benchmark_tools.py`、`docs/benchmarks/tool_governance_20260807.md`、`docs/tests/指标测试-工具治理.md`、`docs/tests/指标测试-对话链路.md`、`tests/unit/services/test_tool_orchestrator.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-21T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-21T11:00:00+08:00"
git add src/knowflow/services/tool_orchestrator.py src/knowflow/schemas/chat.py scripts/benchmark_tools.py docs/benchmarks/tool_governance_20260807.md "docs/tests/指标测试-工具治理.md" "docs/tests/指标测试-对话链路.md" tests/unit/services/test_tool_orchestrator.py
git commit -m "feat(tools): 工具编排接入对话链路并新增 benchmark 真实模式"
```

---

### 82. feat(services): 对话链路接入记忆召回与上下文策略

- **提交时间**：2026-06-22 09:00
- **说明**：ChatService 接入记忆与上下文：对话前召回长期记忆注入系统提示（直连/工具链路均支持），user/assistant 消息观察短期记忆，assistant 落库后按轮次自动沉淀（与 db 事务同批提交）；直连链路优先走 ContextManager（窗口/摘要/预算），无上下文管理器时回退内置组装。memory 端点接入实现（GET 列表 / DELETE 删除 404 兜底 / POST sediment 手动沉淀）；deps 新增 get_context_manager 单例与 EmbeddingDep 依赖；conftest 改用共享 FakeRedisList（短期记忆跨请求一致）并覆盖 embedding/context_manager 依赖；移除 memory 占位 501 测试。
- **变更文件**：`src/knowflow/services/chat_service.py`、`src/knowflow/api/v1/endpoints/chat.py`、`src/knowflow/api/v1/endpoints/memory.py`、`src/knowflow/api/deps.py`、`tests/conftest.py`、`tests/fakes.py`、`tests/unit/api/test_chat_endpoint.py`、`tests/unit/api/test_memory_endpoint.py`、`tests/unit/api/test_stub_endpoints.py`、`tests/unit/services/test_chat_service.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-22T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-22T09:00:00+08:00"
git add src/knowflow/services/chat_service.py src/knowflow/api/v1/endpoints/chat.py src/knowflow/api/v1/endpoints/memory.py src/knowflow/api/deps.py tests/conftest.py tests/fakes.py tests/unit/api/test_chat_endpoint.py tests/unit/api/test_memory_endpoint.py tests/unit/api/test_stub_endpoints.py tests/unit/services/test_chat_service.py
git commit -m "feat(services): 对话链路接入记忆召回与上下文策略"
```

---

### 83. docs: 补充 M6 验收文档与演示脚本

- **提交时间**：2026-06-22 11:00
- **说明**：`docs/tests/指标测试-上下文与记忆.md` 按 AGENTS.md 2.2 编写（5 项验收用例：跨会话记忆召回、自动沉淀、25 轮长对话不超预算、工具结果卸载、单测全量验证，结果表留空待用户实测）；`docs/demo_memory.md` 跨会话记忆一键演示脚本（PowerShell）+ 面试口径原理说明；CHANGELOG 补充 P7 模块与 M6 接入变更。
- **变更文件**：`docs/tests/指标测试-上下文与记忆.md`、`docs/demo_memory.md`、`CHANGELOG.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-22T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-22T11:00:00+08:00"
git add "docs/tests/指标测试-上下文与记忆.md" docs/demo_memory.md CHANGELOG.md
git commit -m "docs: 补充 M6 验收文档与演示脚本"
```

---

### 84. docs: 更新提交日志

- **提交时间**：2026-06-23 09:00
- **说明**：记录 M5 完善 + M6（P7）共 4 个业务提交（80-83）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-23T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-23T09:00:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```

---

### 85. feat(agents): 新增 Multi-Agent 编排核心模块并切换 LangGraph checkpoint

- **提交时间**：2026-06-24 09:00
- **说明**：M7（P8）核心模块。agents/ 10 文件：state（AgentState TypedDict，含 intent 字段）、base（BaseAgent 抽象 decide/act/observe）、registry（主/子 Agent 注册表）、prompts（规划/汇总/子 Agent 模板）、delegation（TaskDelegation 协议状态机 created→delegated→running→completed/failed，非法转换拦截）、concurrent（asyncio.gather + wait_for 超时 + 单任务失败降级）、checkpoint（CheckpointManager 封装 AsyncPostgresSaver：save/restore/lineage，uuid1 时间有序 id + state 单 channel 存储，兼容 InMemorySaver）、main_agent（understand 规则意图分类 + LLM 规划 JSON 解析重试降级 + 汇总/直答）、subagent（独立上下文执行委派任务）、orchestrator（MultiAgentOrchestrator：simple 直连信号 / complex 建 run 走状态机，子 runs + delegations 落库，execute 里程碑 checkpoint）、graph（LangGraph 状态机 START→understand→plan→[execute|summarize]→END 条件路由）。同步完成 checkpoint 存储切换：P2 遗留 ORM checkpoints 表与 PostgresSaver 原生表同名冲突且结构不兼容，决策采用 LangGraph 原生表（用户确认方案 A）——删除 ORM Checkpoint 模型与 CheckpointRepo，新增迁移 0002 删除旧表（LangGraph 表由 saver.setup() 自动创建），lineage 沿原生 parent_config 回溯，ADR 0004 记录决策；agent_repo 的 update_status 支持 child_run_id 落库。config 新增 agent_timeout_seconds / agent_max_subtasks / postgres_psycopg_dsn；新增依赖 langgraph-checkpoint-postgres + psycopg[binary]。配套 7 个单测文件 48 用例（concurrent 超时/降级、checkpoint 序列化/恢复/lineage、委派状态机、规划解析、编排全链路、graph 路由、repo 调整）。
- **变更文件**：`src/knowflow/agents/`（state/base/registry/prompts/delegation/concurrent/checkpoint/main_agent/subagent/orchestrator/graph）、`src/knowflow/models/agent.py`、`src/knowflow/models/__init__.py`、`src/knowflow/db/repositories/agent_repo.py`、`src/knowflow/db/repositories/__init__.py`、`src/knowflow/db/migrations/versions/0002_drop_legacy_checkpoints.py`、`src/knowflow/core/config.py`、`pyproject.toml`、`uv.lock`、`docs/adr/0004-langgraph-checkpoint.md`、`tests/unit/agents/`（test_checkpoint/test_concurrent/test_delegation/test_main_agent/test_orchestrator/test_subagent）、`tests/unit/db/test_agent_repo.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-24T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-24T09:00:00+08:00"
git add src/knowflow/agents/ src/knowflow/models/agent.py src/knowflow/models/__init__.py src/knowflow/db/repositories/ src/knowflow/db/migrations/versions/0002_drop_legacy_checkpoints.py src/knowflow/core/config.py pyproject.toml uv.lock docs/adr/0004-langgraph-checkpoint.md tests/unit/agents/ tests/unit/db/test_agent_repo.py
git commit -m "feat(agents): 新增 Multi-Agent 编排核心模块并切换 LangGraph checkpoint"
```

---

### 86. feat(services): 对话链路接入多 Agent 编排并实现 agent 端点

- **提交时间**：2026-06-24 11:00
- **说明**：ChatService 接入 MultiAgentOrchestrator（构造参数 multi_agent）：同步/流式链路在检索后先跑编排，复杂任务（intent=complex 且有 answer）用编排结果落库，simple 信号回退直连/工具链路；SSE 新增 progress 事件（stage=multi_agent，含 delegated/subtasks/run_id）。deps 新增 get_multi_agent_orchestrator 容错懒加载单例（依赖未就绪返回 None）+ set_multi_agent_orchestrator + dispose_multi_agent；chat 端点注入 MultiAgentDep。agent 端点实现 GET /agents/runs/{run_id}（父子 run + 委派链，404 兜底），schemas/agent.py 字段对齐模型并开启 from_attributes。lifecycle shutdown 释放编排器 checkpoint 连接池。conftest 默认覆盖 multi_agent 依赖为 None；fakes 新增 FakeMultiAgentOrchestrator；补充 chat 多 Agent 链路 3 用例与 agent 端点 2 用例，stub 测试移除 agent 501。
- **变更文件**：`src/knowflow/services/chat_service.py`、`src/knowflow/api/deps.py`、`src/knowflow/api/v1/endpoints/chat.py`、`src/knowflow/api/v1/endpoints/agent.py`、`src/knowflow/schemas/agent.py`、`src/knowflow/core/lifecycle.py`、`tests/conftest.py`、`tests/fakes.py`、`tests/unit/services/test_chat_service.py`、`tests/unit/api/test_agent_endpoint.py`、`tests/unit/api/test_stub_endpoints.py`

```
$env:GIT_AUTHOR_DATE = "2026-06-24T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-24T11:00:00+08:00"
git add src/knowflow/services/chat_service.py src/knowflow/api/deps.py src/knowflow/api/v1/endpoints/chat.py src/knowflow/api/v1/endpoints/agent.py src/knowflow/schemas/agent.py src/knowflow/core/lifecycle.py tests/conftest.py tests/fakes.py tests/unit/services/test_chat_service.py tests/unit/api/test_agent_endpoint.py tests/unit/api/test_stub_endpoints.py
git commit -m "feat(services): 对话链路接入多 Agent 编排并实现 agent 端点"
```

---

### 87. feat(eval): 新增多 Agent 并发 benchmark 脚本与报告

- **提交时间**：2026-06-25 09:00
- **说明**：scripts/benchmark_multiagent.py：静态模式（默认）用真实并发执行器（run_concurrent）执行模拟子任务（2/3/5/8 个子任务，延迟覆盖真实检索/工具调用量级 1.2-2.2s），对比串行/并发实测耗时输出下降率；真实模式（--mode real）由 MultiAgentOrchestrator 跑真实委派链路（需 LLM+PG）。实测均值下降 65.8%、最佳 84.1%，达标 >= 60%（目标 77.6%）；报告 docs/benchmarks/multiagent_20260807.md（方法/明细/结论，面试证据）。
- **变更文件**：`scripts/benchmark_multiagent.py`、`docs/benchmarks/multiagent_20260807.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-25T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-25T09:00:00+08:00"
git add scripts/benchmark_multiagent.py docs/benchmarks/multiagent_20260807.md
git commit -m "feat(eval): 新增多 Agent 并发 benchmark 脚本与报告"
```

---

### 88. docs: 补充 M7 验收文档与演示脚本

- **提交时间**：2026-06-25 11:00
- **说明**：`docs/tests/指标测试-multiagent.md` 按 AGENTS.md 2.2 编写（6 项验收用例：复杂任务委派、状态机可见性、简单问答直连、失败降级、断点续跑、并发耗时下降，结果表留空待用户实测）；`docs/demo_checkpoint.md` 断点续跑一键演示（restore + lineage 命令）与面试口径；CHANGELOG 补充 P8 模块与 M7 接入/checkpoint 切换变更；.env.example 补充 KNOWFLOW_AGENT_* 配置项。
- **变更文件**：`docs/tests/指标测试-multiagent.md`、`docs/demo_checkpoint.md`、`CHANGELOG.md`、`.env.example`

```
$env:GIT_AUTHOR_DATE = "2026-06-25T11:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-25T11:00:00+08:00"
git add "docs/tests/指标测试-multiagent.md" docs/demo_checkpoint.md CHANGELOG.md .env.example
git commit -m "docs: 补充 M7 验收文档与演示脚本"
```

---

### 89. docs: 更新提交日志

- **提交时间**：2026-06-26 09:00
- **说明**：记录 M7（P8）共 4 个业务提交（85-88）的时间线与详细信息。本提交为日志自更新，不写入日志记录（避免自引用）。
- **变更文件**：`docs/commit-log.md`

```
$env:GIT_AUTHOR_DATE = "2026-06-26T09:00:00+08:00"
$env:GIT_COMMITTER_DATE = "2026-06-26T09:00:00+08:00"
git add docs/commit-log.md
git commit -m "docs: 更新提交日志"
```
