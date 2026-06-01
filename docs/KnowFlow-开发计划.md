# KnowFlow 项目开发计划

> 目标：按本计划逐步开发，最终交付一个**真实可运行、工程规范完整、可复现量化指标**的企业知识库 Agent 平台，直接用于 Agent 开发岗位面试。
> 版本：v1.0 ｜ 2026-08-05 ｜ 配套文档：《KnowFlow 项目设计文档》《KnowFlow 项目结构》

---

## 一、前置说明

### 1.1 开发环境

| 项 | 要求 |
|---|---|
| OS | Windows 11 / macOS / Linux 均可 |
| Python | 3.13（`.python-version` 锁定） |
| 包管理 | uv（`pip install uv` 或官方安装脚本） |
| 容器 | Docker Desktop（本地依赖 PG/Milvus/Redis/MinIO 用 docker-compose 启动） |
| LLM API | OpenAI 兼容接口（DeepSeek / Qwen / OpenAI，需一个 API Key） |
| Embedding | 开源模型（如 `BAAI/bge-m3`，本地跑，sentence-transformers）或 API |

### 1.2 配套文档关系

- **做什么** →《KnowFlow 项目设计文档》（PRD / 架构 / 模块设计 / API / 指标）
- **目录长什么样** →《KnowFlow 项目结构》（目录树，结构变更以此为准）
- **按什么顺序做、怎么验收** → 本文档（开发计划）

### 1.3 开发原则

1. **每阶段可验收**：一个 Phase 做完，跑验收命令通过后，再进入下一 Phase。
2. **先跑通再优化**：先实现最小可用链路，再补细节（如 reranker 先接简单的，再换 cross-encoder）。
3. **指标可复现**：所有量化指标（8% / 34.2% / 32.6% / 94+% / 77.6%）必须有脚本 + 数据 + 报告三件套，禁止拍脑袋填数。
4. **每个 Phase 结束时 git 提交**，commit message 遵循 Conventional Commits。

---

## 二、全局工程规范（所有 Phase 通用，必须遵守）

### 2.1 代码质量门禁

```toml
# pyproject.toml 必须包含以下配置段
[tool.ruff]
line-length = 100
target-version = "py313"
src = ["src", "tests", "scripts", "worker"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "C4", "RUF"]
# tests 允许断言风格与裸 except 提示
[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]

[tool.mypy]
python_version = "3.13"
check_untyped_defs = true
disallow_untyped_defs = true
warn_return_any = true
warn_unused_ignores = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-q --cov=src --cov-report=term-missing"
```

**门禁命令（每次代码变更后必须执行，全绿才算完成）：**

```bash
uv run ruff check src/ tests/ scripts/ worker/     # 0 errors
uv run ruff format --check src/ tests/ scripts/ worker/   # 格式通过
uv run mypy src/ worker/                            # 0 errors
uv run pytest tests/unit -q                         # 全绿
```

### 2.2 pre-commit（`.pre-commit-config.yaml`）

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        args: [src/, worker/]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
```

### 2.3 提交规范（Conventional Commits）

```
feat(retrieval): add hybrid search with RRF fusion
fix(tools): resolve circular dependency in skill loader
test(context): add spiller threshold unit tests
docs(adr): record decision on checkpoint storage
chore: bump langgraph to 0.2.40
```

### 2.4 每个 Phase 的标准工作流

```
1. 阅读该 Phase 任务清单与对应设计文档章节
2. 实现代码（按结构文档的目录落文件）
3. 执行 2.1 门禁命令，全绿
4. 编写/补充该阶段测试，uv run pytest 全绿
5. pre-commit run --all-files
6. git commit（Conventional Commits）
7. 执行本 Phase 验收标准，记录结果（指标类存 eval/reports/ 或 docs/benchmarks/）
```

### 2.5 测试规范

| 层级 | 目录 | 要求 |
|---|---|---|
| unit | tests/unit/ | mock 外部存储，不依赖容器；覆盖核心算法（分块/融合/扩展/精排/域隔离/卸载/并发） |
| integration | tests/integration/ | 真实容器依赖，验证跨模块链路 |
| e2e | tests/e2e/ | 完整服务 + 真实模型，跑通 SSE 流式 |
| 覆盖率 | — | 单元测试核心模块覆盖率 ≥ 70%，整体 ≥ 60%，`uv run pytest --cov` 查看 |

---

## 三、Phase 总览

```
P0 脚手架 ─▶ P1 基础设施 ─▶ P2 数据模型 ─┬─▶ P3 GraphRAG 检索 ─▶ P5 对话链路 ─┬─▶ P8 编排
                                         └─▶ P4 API+文档服务 ────────────────┴─▶ P10 可观测/评测
                                                                   │
                                        P6 工具治理 ◀──────────────┤
                                        P7 上下文+记忆 ◀───────────┤
                                        P9 沙盒文件系统 ◀──────────┘
P11 工程化收尾（面试就绪）
```

| Phase | 名称 | 预计 | 优先级 | 里程碑 |
|---|---|---|---|---|
| P0 | 项目脚手架与工程规范 | 0.5-1 天 | 必做 | M1 |
| P1 | 核心基础设施与本地依赖 | 1-2 天 | 必做 | M1 |
| P2 | ORM 模型、迁移与 Repository | 1-2 天 | 必做 | M1 |
| P3 | GraphRAG 检索模块 | 3-4 天 | 必做（核心亮点） | M2 |
| P4 | API 层、文档服务与异步索引 | 2-3 天 | 必做 | M3 |
| P5 | 对话链路与 SSE 流式 | 2-3 天 | 必做 | M4 |
| P6 | 工具治理与 Skill 体系 | 2-3 天 | 必做（核心亮点） | M5 |
| P7 | 上下文工程与记忆 | 2-3 天 | 必做 | M6 |
| P8 | Multi-Agent 编排 | 2-3 天 | 必做（核心亮点） | M7 |
| P9 | 沙盒文件系统 | 1-2 天 | 必做 | M5 |
| P10 | 可观测、离线评测与指标复现 | 2-3 天 | 必做（指标来源） | M8 |
| P11 | 工程化收尾与面试就绪 | 2-3 天 | 必做 | M8 |

### 里程碑分组（合并建议）

12 个 Phase 合并为 8 个里程碑，每个里程碑都是一个“可停下、可验收、可讲述”的节点：

| 里程碑 | 包含 Phase | 名称 | 预计 | 分组理由 |
|---|---|---|---|---|
| M1 | P0 + P1 + P2 | 项目底座：脚手架 + 基础设施 + 数据模型 | 3-4 天 | 同属地基层，验收机械，一次完成 |
| M2 | P3 | GraphRAG 检索 | 3-4 天 | 核心亮点，评测集与指标需专注验收 |
| M3 | P4 | API 层与异步索引 | 2-3 天 | 内容独立 |
| M4 | P5 | 对话链路与 SSE 流式 | 2-3 天 | 最小可用闭环里程碑 |
| M5 | P6 + P9 | 工具治理与沙盒文件系统 | 3-4 天 | file_tools 直接接真实沙盒，避免占位返工 |
| M6 | P7 | 上下文工程与记忆 | 2-3 天 | 内容量大，独立验收 |
| M7 | P8 | Multi-Agent 编排 | 2-3 天 | 核心亮点，依赖 M4/M5 完成 |
| M8 | P10 + P11 | 评测复现与面试就绪 | 4-5 天 | 收尾性质，指标汇总 + 工程化 |

> 推进顺序即 M1 → M8；里程碑完成 = 其内部各 Phase 验收标准全部通过。单独进行的 Phase 即为独立里程碑。

> 总工期约 21-30 天。若时间紧张，裁剪顺序：P9 简化为最小实现 → P11 中 k8s 部分简化 → P8 只做单委派场景。

---

## 四、Phase 详细计划

### P0 · 项目脚手架与工程规范

**对应设计文档**：3.7 环境与依赖管理；《项目结构》根目录部分

**任务清单**：

1. 在仓库根目录初始化：`uv init --python 3.13`（当前工作区已存在 pyproject.toml，直接补充）
2. 编写完整 `pyproject.toml`：
   - `[project]`：name = "knowflow"、version = "0.1.0"、requires-python = ">=3.13"
   - 全部运行时依赖（按设计文档 3.7，**仅保留 asyncpg，删除 psycopg2-binary**，async 栈只需 asyncpg）
   - `[dependency-groups]` dev：pytest / pytest-asyncio / pytest-cov / ruff / mypy / pre-commit / httpx
   - 2.1 节全部 `[tool.*]` 配置段
3. 创建根目录文件：`.gitignore`（含 .venv/、__pycache__/、.env、dist/、.coverage、htmlcov/）、`.editorconfig`、`.python-version`、`.env.example`、`.pre-commit-config.yaml`（2.2 节）、`Makefile`、`LICENSE`、`CHANGELOG.md`（初始条目）、`README.md`（占位，P11 完善）
4. 按《项目结构》创建全部目录骨架与 `__init__.py`（src/knowflow/ 下所有子包 + worker/ + tests/ 分层目录 + skills/ + eval/ + scripts/ + deploy/ + docs/adr/）
5. `docker-compose.yml`：postgres:16 / milvusdb/milvus:v2.4.0 / redis:7 / minio/minio（按设计文档 3.7，补全卷与健康检查）
6. 安装并验证：`uv sync`、`uv run pre-commit install`
7. git init + 首次提交

**验收标准**（全部通过才算完成）：

```bash
uv sync                                # 成功，uv.lock 生成
uv run ruff check src/ tests/          # 0 errors
uv run ruff format --check .           # 通过
uv run mypy src/                       # 0 errors
uv run pytest tests/unit -q            # 空跑通过（1 passed）
uv run pre-commit run --all-files      # 全部 hook 通过
docker compose config                  # 四服务配置合法
uv run python -c "import knowflow"     # 包可导入
```

---

### P1 · 核心基础设施与本地依赖

**对应设计文档**：3.1 技术栈、3.6 设计决策 D4/D7；《项目结构》core/、db/ 外层

**任务清单**：

1. `core/config.py`：pydantic-settings `Settings`，环境变量前缀 `KNOWFLOW_`，字段至少包含：
   - 应用：app_name / env / debug / log_level / api_prefix
   - PostgreSQL：postgres_dsn（或 host/port/user/password/db 拆分）
   - Redis：redis_url
   - Milvus：milvus_uri
   - MinIO：minio_endpoint / minio_access_key / minio_secret_key / minio_bucket
   - LLM：llm_api_key / llm_base_url / llm_model / embedding_model / reranker_model
   - 上下文：context_budget_tokens / spill_threshold_tokens / window_max_turns
   - 存储：session_ttl_seconds / workspace_quota_bytes
   - `get_settings()` 单例 + 测试环境覆盖机制（`KNOWFLOW_ENV=test`）
2. `core/constants.py`：执行域枚举（DOMAIN_DIRECT/SKILL_ONLY/SUBAGENT_ONLY/INTERNAL）、任务状态枚举、SSE 事件类型枚举、错误码前缀常量
3. `core/exceptions.py`：`AppError` 基类（error_code + message + status_code）+ 子类（NotFoundError / PermissionDeniedError / ToolExecutionError / RateLimitError / ContextOverflowError）
4. `core/logging.py`：structlog 配置（JSON 输出 + request_id 上下文绑定），测试环境输出控制台
5. `core/lifecycle.py`：FastAPI lifespan（启动建连接池：PG/Redis/Milvus/MinIO；关闭优雅释放）
6. `core/telemetry.py`：OpenTelemetry 初始化（trace provider + span processor 挂到 collector/store），P10 前先留接口
7. `db/base.py`：SQLAlchemy async engine + async_sessionmaker + `get_db()` 依赖
8. `db/redis.py` / `db/milvus.py` / `db/minio.py`：各连接封装（连接池、ping、异常包装）
9. `docker compose up -d` 启动四件套，编写 `scripts/check_env.py`（逐个探测依赖连通性）
10. `.env.example` 填满 P1 全部配置项并加注释

**验收标准**：

```bash
docker compose up -d && docker compose ps     # 4 个服务 healthy
uv run python scripts/check_env.py            # 全部输出 ✓
uv run python -c "from knowflow.core.config import get_settings; print(get_settings().llm_model)"
uv run pytest tests/unit -q                   # 新增 config/exceptions/logging 单测全绿
uv run ruff check src/ && uv run mypy src/    # 0 errors
```

---

### P2 · ORM 模型、迁移与 Repository

**对应设计文档**：3.4 模块一/三/六的数据表设计；《项目结构》models/、db/repositories/

**关键决策（先定后写，P0 遗留问题的解决）**：

- **checkpoint 存储**：`checkpoints` 表建在 PostgreSQL（与 3.4 表设计一致），Redis 只做会话级热缓存，不存 checkpoint 本体。写入 `docs/adr/0003-checkpoint-storage.md` 记录此决策。
- **补齐 3.4 缺失的表**：documents / chunks / document_indexes、sessions / messages / turns、tool_calls / skill_activations / tool_metrics、eval_datasets / eval_runs / eval_results，字段与设计文档已有表风格一致，`created_at` 统一 TIMESTAMPTZ。

**任务清单**：

1. `models/base.py`：DeclarativeBase + `TimestampMixin`（created_at/updated_at）
2. 按《项目结构》models/ 清单实现 9 个模型文件（document/graph/session/agent/tool/memory/trace/eval 共约 13 个模型类），建立外键关系与索引
3. Alembic 初始化 + 生成首个迁移：`uv run alembic revision --autogenerate -m "init schema"`，检查生成的迁移 SQL 符合设计（尤其 entities/relations/agent_runs/task_delegations/checkpoints/long_term_memories/trace_spans 与 3.4 一致）
4. `scripts/init_db.py`：建库 + `alembic upgrade head` 封装
5. `db/repositories/` 实现 5 个 repo：document_repo（文档/分块 CRUD + 分页）、graph_repo（实体/关系 upsert + **一跳扩展 SQL**）、session_repo（会话/消息）、agent_repo（run/委派/checkpoint 层级查询）、trace_repo（写入/按 trace_id 查询）
6. 单测：每个 repo 用 SQLite+aiosqlite（或 testcontainers PG，推荐前者简单）验证 CRUD 与一跳扩展 SQL 正确性

**验收标准**：

```bash
uv run python scripts/init_db.py                    # 建库 + 迁移成功
uv run alembic current                              # 显示 head
uv run pytest tests/unit -q                         # repo 单测全绿（含一跳扩展 JOIN 用例）
uv run ruff check src/ && uv run mypy src/          # 0 errors
# 手工验证（psql 或 python）：插入 2 个 chunk + 实体 + 关系，执行一跳扩展 SQL 返回正确关联 chunk
```

---

### P3 · GraphRAG 检索模块（核心亮点一）

**对应设计文档**：3.4 模块一、2.5 指标（Recall@10 +8%）；《项目结构》retrieval/

**任务清单**：

1. `indexer/`：parser 调度 + pdf/docx/markdown/text 四类解析器（PyMuPDF / python-docx / markdown 库）、splitter（递归分块，默认 chunk_size=512、overlap=64，参数进配置）、cleaner（空白规范化/去噪）
2. `embedding.py`：EmbeddingClient 封装（sentence-transformers `BAAI/bge-m3` 本地或 API 兼容），批量接口 + 维度写入配置
3. `entity_extractor.py`：LLM 抽取（JSON 输出 schema：entities[{name,type}] + relations[{source,target,relation_type}]），异常重试 + 输出解析兜底，实体归一（小写化/别名表）
4. `graph_store.py` / `vector_store.py` / `bm25_store.py`：分别对接 PG 图谱表、Milvus collection（script `init_milvus.py` 建 collection + 索引）、PG tsvector 全文索引
5. `hybrid_search.py`：向量 + BM25 双路召回 → **RRF 融合**（k=60 经典参数），返回统一 ChunkScore
6. `expander.py`：从召回 chunk 提取实体 ID → `graph_repo.one_hop_expand` → 召回关联 chunk → 去重合并（保留原始分数）
7. `reranker.py`：cross-encoder（`BAAI/bge-reranker-v2-m3` 本地或 API），对 (query, chunk) 打分重排，默认 top_k=10
8. `retriever.py`：`GraphRAGRetriever` 统一入口（hybrid → expand → rerank），返回带来源元数据的检索结果
9. `cache.py`：query hash + TTL 缓存（Redis），命中跳过全链路
10. `pipeline.py`：`RetrievalPipeline.index_document()` 编排完整索引链路（解析→分块→embedding→实体抽取→三写入库），支持增量/重建
11. **评测集**：构建 `eval/datasets/retrieval_eval.jsonl`（50-100 条：query + 相关 chunk_id 标注，用 3-5 篇真实业务文档如产品手册/HR 政策做语料）
12. `eval/scripts/compare_baseline.py`：同一评测集上对比纯 Hybrid vs GraphRAG（hybrid+扩展），输出 Recall@10/MRR 对比表与提升幅度

**验收标准**：

```bash
uv run python scripts/init_milvus.py                # collection 创建成功
# 上传 3 篇真实文档完成索引（先走 pipeline.py 脚本直调，P4 接 API）
uv run pytest tests/unit/retrieval -q               # splitter/extractor/graph_store/hybrid/expander/reranker 全绿
uv run python eval/scripts/compare_baseline.py      # 输出对比报告：GraphRAG 相对 Hybrid Recall@10 提升 ≥ 8%
# 报告存入 eval/reports/compare_2026xxxx.md（面试证据）
uv run ruff check src/ && uv run mypy src/          # 0 errors
```

**面试要点**：能讲清 RRF 原理、一跳扩展的 SQL、评测集怎么标注的（ground truth 从哪来）、为什么用 PG 不用 Neo4j。

---

### P4 · API 层、文档服务与异步索引

**对应设计文档**：3.5 API 设计；《项目结构》schemas/、api/、services/、tasks/、worker/

**任务清单**：

1. `schemas/` 全部 8 个文件：common（统一响应 `{code, message, data}` + 分页）、chat、document、agent、tool、memory、trace、eval（字段对齐设计文档 3.5 与 3.4 模块设计）
2. `api/deps.py`：`get_db` / `get_redis` / `get_settings` 依赖 + 租户上下文（先简单 header 透传，P11 补鉴权细节）
3. `api/middleware.py`：请求 ID 生成（绑定 structlog 上下文）、访问日志、限流（Redis 固定窗口，默认 60 req/min/ip）、CORS
4. `api/sse.py`：SSE 事件封装（事件类型 token/tool_start/tool_end/retrieval/progress/done/error + 心跳 + 客户端断开检测）
5. `api/router.py` + `api/v1/router.py` + `api/v1/endpoints/` 9 个端点模块：
   - chat（POST /chat、POST /chat/stream，P5 接实现）
   - document（上传/列表/删除/reindex，上传先落 MinIO 原始文件，**异步索引**）
   - knowledge（知识库 CRUD + 检索接口，调 retriever）
   - agent / skill / memory / trace / eval（先实现列表/查询等只读接口，P5-P10 逐步接实现）
   - health（/healthz 存活 + /readyz 就绪，探测依赖连通）
6. `services/document_service.py`：上传 → 校验格式/大小 → 存 MinIO → 入 documents 表 → 发索引任务
7. `tasks/broker.py`：Redis Stream 任务队列封装（XADD/XREADGROUP，消费组、ack、失败重试 3 次）
8. `tasks/index_task.py`：消费索引任务 → 调 `RetrievalPipeline.index_document()` → 更新 document 状态（pending→indexing→ready/failed）
9. `worker/main.py` + `worker/settings.py`：独立进程启动（消费组循环 + 优雅退出 + structlog）
10. `api/v1/endpoints/document.py` 接 document_service；`knowledge.py` 接 retriever 只读检索

**验收标准**：

```bash
docker compose up -d && uv run uvicorn knowflow.main:app --reload
curl http://localhost:8000/api/v1/health/readyz                    # {"status":"ok"} 探测依赖
curl -X POST -F "file=@docs/测试文档.pdf" http://localhost:8000/api/v1/documents/upload
curl http://localhost:8000/api/v1/documents                         # 文档列表，状态 pending→indexing→ready
# 启动 worker 后索引任务被消费，文档转 ready，Milvus/PG 有数据
curl -X POST http://localhost:8000/api/v1/knowledge/search -H "Content-Type: application/json" -d '{"query":"..."}'
# 返回 top_k 检索结果
uv run pytest tests/integration/test_index_pipeline.py -q           # 全绿
uv run python scripts/gen_openapi.py                                 # 生成 openapi.json
```

---

### P5 · 对话链路与 SSE 流式

**对应设计文档**：3.4 模块六 SSE、2.6 非功能指标（首 Token < 800ms）；《项目结构》services/chat_service.py

**任务清单**：

1. `services/chat_service.py` 主流程（无工具版先行）：
   - 会话存在性检查 → 消息入库 → 检索（retriever.retrieve）→ 组装 prompt → LLM 流式生成 → 消息/引用落库
   - 返回结构含 `citations`（检索来源 chunk 元数据）
2. SSE 事件序列：`retrieval`（召回结果）→ `token`（流式 token 流）→ `done`（含引用与耗时统计）;异常时 `error` 事件
3. `api/v1/endpoints/chat.py` 接 chat_service，/chat/stream 用 sse.py 封装；/chat 同步版返回完整响应
4. 多轮会话：messages/turns 表读写，历史注入（P7 前先全量注入最近 N 轮）
5. `core/lifecycle.py` 完善：LLM/embedding/reranker 客户端懒加载单例
6. e2e 测试 `tests/e2e/test_chat_stream_e2e.py`：真实模型跑通 1 个完整 QA 流（断言事件序列与内容非空）

**验收标准**：

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"介绍一下公司报销流程"}'          # 看到 retrieval→token...→done 完整事件流
# 首 token 时间 < 800ms（脚本计时，记录到 docs/benchmarks/）
uv run pytest tests/e2e/test_chat_stream_e2e.py -q                  # 全绿
# 多轮追问（同一 session_id）能引用上文
```

---

### P6 · 工具治理与 Skill 体系（核心亮点二）

**对应设计文档**：3.4 模块二、2.5 指标（可见工具数 -34.2%、Schema Token -32.6%、FC 准确率 94+%）；《项目结构》tools/、skills/

**任务清单**：

1. `tools/base.py`：`BaseTool` 抽象（name/description/input_schema(Pydantic)/execute），统一返回 ToolResult(tool_name/success/output/token_usage/latency)
2. `tools/registry.py`：ToolRegistry（register/get/list_by_domain）
3. `tools/builtin/` 4 个工具：retrieval_tool（调 retriever）、file_tools（沙盒读写，P9 接实现，先抛 NotSupported）、search_tool（网络搜索，可用 duckduckgo-search 库）、calculator（安全 eval 表达式，白名单）
4. `tools/skill_schema.py` + `skill_loader.py`：SkillDefinition（name/description/tools/dependencies/domain/enabled）+ YAML frontmatter 解析与校验（参考设计文档 3.4 示例）
5. `tools/dependency_resolver.py`：依赖解析 + 拓扑排序，检测循环/缺失依赖
6. `tools/domain.py` + `visibility.py`：四类执行域；`compute(active_skills, agent_role)` 输出可见工具集（direct 恒可见 + skill_only 按激活 + subagent_only 按角色 + internal 永不可见）
7. `tools/injector.py`：按可见集构建 LLM tools 参数（JSON Schema 注入）
8. `tools/permission.py`：运行时越权拦截（执行域不符 → 拒绝 + 记 trace + 抛 ToolExecutionError）
9. `tools/metrics.py`：记录每次调用（成功/失败/token/耗时），提供 `stats()`（可见数均值、Schema Token 总量、准确率）
10. `skills/` 4 个 Skill：knowledge_qa / document_summary / data_analysis / code_review 的 SKILL.md（frontmatter 按 schema 填写）
11. `services/chat_service.py` 升级：工具版对话链路（意图识别 → Skill 激活 → 注入可见工具 → LLM 工具调用循环 → 结果回填 → 继续生成），最大 5 轮工具循环
12. `api/v1/endpoints/skill.py` 接完整实现（列表/启停/配置）
13. **指标脚本** `scripts/benchmark_tools.py`：对比"全量工具注入 vs 执行域隔离注入"的可见工具数与 Schema Token 数，输出下降百分比；用 30+ 条工具调用场景统计 FC 准确率

**验收标准**：

```bash
curl http://localhost:8000/api/v1/skills                        # 4 个 Skill
curl -X PUT http://localhost:8000/api/v1/skills/data_analysis/toggle   # 启停生效
# 对话触发工具调用（如"帮我算 2^10"，应触发 calculator 并返回 1024）
uv run pytest tests/unit/tools -q                               # loader/domain/visibility/dependency_resolver 全绿
uv run python scripts/benchmark_tools.py                        # 输出：可见工具数 -34.2%、Schema Token -32.6%、FC 准确率 94+%
# 结果存 docs/benchmarks/tool_governance_2026xxxx.md（面试证据）
uv run ruff check src/ && uv run mypy src/                      # 0 errors
```

**面试要点**：能讲清执行域设计动机（Token 浪费 vs 准确率）、Skill 声明式加载为什么比硬编码好、指标统计口径。

---

### P7 · 上下文工程与记忆

**对应设计文档**：3.4 模块四/模块六记忆部分、2.5 指标（跨会话记忆）；《项目结构》context/、memory/

**任务清单**：

1. `context/token_counter.py`：tiktoken 计数（模型名映射，缺失回退字符估算）
2. `context/budget.py`：上下文预算分配（系统/历史/工具/检索/记忆各模块配额，总量 = context_budget_tokens）
3. `context/window.py`：滑动窗口（保留最近 N 轮，超限截断，默认 window_max_turns=20）
4. `context/summarizer.py`：LLM 历史摘要（增量 compact，保留关键信息清单）
5. `context/spiller.py`：工具结果超阈值（默认 spill_threshold_tokens=4000）→ 写入沙盒文件（P9 前先落本地临时目录占位接口）→ 用 `{"spilled": true, "path": "/workspace/..."}` 引用替换
6. `context/manager.py` + `builder.py` + `strategy.py`：编排策略（超预算时顺序：摘要 → 卸载 → 截断），按任务类型选择策略
7. `memory/short_term.py`：Redis 会话记忆（TTL=session_ttl_seconds）
8. `memory/importance.py`：信息重要性打分（LLM 打分 0-10 + 规则兜底）
9. `memory/compressor.py`：长期记忆压缩（摘要 + 关键信息提取）
10. `memory/long_term.py` + `store.py` + `recall.py`：PG 持久化 + embedding 向量召回（相关度 + 时间衰减，last_recall 参与排序）
11. `memory/manager.py`：`sediment()`（会话结束/每 5 轮从短期沉淀高价值信息入长期）+ `recall(query)` 注入对话
12. `chat_service` 接入：记忆召回结果注入系统提示 + 上下文策略生效
13. `api/v1/endpoints/memory.py` 接实现（查询/删除/手动压缩）

**验收标准**：

```bash
# 长对话场景：连续 25 轮提问，第 25 轮响应不超预算（观察 trace 中 context 指标）
# 工具结果卸载：触发超阈值工具结果（如搜索返回长文本），响应中该结果被替换为 /workspace/ 引用且仍可回答
uv run pytest tests/unit/context tests/unit/memory -q            # window/summarizer/spiller/long_term/recall 全绿
# 跨会话记忆：会话 A 声明偏好，会话 B 提问能召回并体现（记录演示脚本 docs/demo_memory.md）
```

---

### P8 · Multi-Agent 编排（核心亮点三）

**对应设计文档**：3.4 模块三、2.5 指标（并发较串行 -77.6%）；《项目结构》agents/

**关键决策（先定后写）**：

- **LangGraph checkpoint 取舍**：采用 LangGraph 原生 checkpoint（BaseCheckpointSaver + PostgresSaver），在其上扩展父子关系字段（parent_checkpoint_id）实现 lineage 追踪，不自研 CheckpointManager 全套。写入 `docs/adr/0004-langgraph-checkpoint.md`（面试可讲：为什么站在 LangGraph 肩上而非重复造轮子）。

**任务清单**：

1. `agents/state.py`：AgentState（messages/tool_calls/subtasks/context_budget/active_skills）
2. `agents/base.py` + `registry.py`：BaseAgent 抽象（decide/act/observe）+ 主/子 Agent 注册表
3. `agents/prompts.py`：主 Agent 规划 prompt（判断是否需要委派）+ 子 Agent 执行 prompt + 汇总 prompt
4. `agents/graph.py`：LangGraph 状态机（START → understand → plan → [delegate] → execute → summarize → END），条件路由（是否委派）
5. `agents/main_agent.py`：规划/委派/汇总；`agents/subagent.py`：独立 ContextManager 实例执行委派任务
6. `agents/delegation.py`：TaskDelegation 协议（状态机 created→delegated→running→completed/failed，落 task_delegations 表）
7. `agents/orchestrator.py` + `concurrent.py`：asyncio.gather 并发执行 + 超时（默认 60s）+ 降级（单子失败不阻塞，结果标记 failed）
8. `agents/checkpoint.py`：封装 PostgresSaver + 父子 checkpoint 写入（parent_checkpoint_id），提供 lineage 查询
9. `services/chat_service.py` 接入：复杂任务（多子任务可拆）走编排，简单问答直连检索
10. `api/v1/endpoints/agent.py` 接实现（run 状态/委派记录查询）
11. `scripts/benchmark_multiagent.py`：同任务集对比串行 vs 并发端到端耗时，输出下降百分比
12. 单测：orchestrator（并发/超时/降级）、checkpoint（序列化/恢复/lineage）、concurrent

**验收标准**：

```bash
# 构造多子任务场景（如"对比 A/B/C 三款产品的价格与参数并汇总"）触发委派
curl http://localhost:8000/api/v1/agents/runs/{run_id}            # 状态机可见父子 run 记录与委派链
uv run pytest tests/unit/agents -q                                # 全绿
uv run python scripts/benchmark_multiagent.py                     # 输出：并发较串行耗时下降 ≥ 60%（目标 77.6%）
# 结果存 docs/benchmarks/multiagent_2026xxxx.md
# 断点续跑：kill 后从 checkpoint 恢复继续（记录演示步骤 docs/demo_checkpoint.md）
```

---

### P9 · 沙盒文件系统

**对应设计文档**：3.4 模块五；《项目结构》sandbox/

**任务清单**：

1. `sandbox/workspace.py`：WorkspaceManager（会话级 workspace 创建/清理，MinIO key 前缀 `sessions/{sid}/workspace/`）
2. `sandbox/virtual_path.py`：虚拟路径映射（`/workspace/x.json` ↔ MinIO key）
3. `sandbox/access_control.py`：路径校验（拦截 `../`、绝对路径、跨会话访问）+ 白名单
4. `sandbox/file_ops.py`：read/write/list/delete/exists
5. `sandbox/minio_backend.py`：对象 CRUD 封装
6. `sandbox/quota.py` + `lifecycle.py`：配额（默认单会话 100MB，可配置）+ TTL 清理（会话结束/过期）
7. `tools/builtin/file_tools.py` 接真实实现（read/write/list 走沙盒）
8. `context/spiller.py` 切换真实沙盒后端（替换 P7 的临时目录占位）

**验收标准**：

```bash
uv run pytest tests/unit/sandbox -q                               # 全绿
# 安全用例：write("../../etc/passwd") 被拦截；会话 A 无法读会话 B 文件
# 对话触发：让工具写文件（如 data_analysis 导出 CSV），响应中可引用 /workspace/xxx.csv 且可通过 file_tools 读回
```

---

### P10 · 可观测、离线评测与指标复现

**对应设计文档**：3.4 模块六 Trace/Replay/评测、2.5 全部指标；《项目结构》observability/、eval/

**任务清单**：

1. `observability/span.py` + `tracer.py`：Span 数据模型（agent_decision/tool_call/retrieval/memory_recall）+ 嵌套 span + 上下文传播（trace_id 贯穿请求）
2. `observability/collector.py` + `store.py`：异步批量写 PG（不阻塞主流程）+ 查询接口
3. `observability/replay.py`：按 checkpoint + trace 重放会话（恢复状态 + 按时间序重放事件）
4. `api/v1/endpoints/trace.py` 接实现（按 session 查询 / replay 触发）
5. `observability/eval/`：runner（跑评测集）/ dataset（加载/校验）/ metrics（Recall@K/MRR/NDCG/FC 准确率）/ report（Markdown 报告生成）
6. `eval/datasets/knowledge_qa_eval.jsonl`：50-100 条 QA 对（含参考答案要点 + 相关 chunk 标注）
7. `eval/scripts/run_eval.py`：统一评测入口（检索评测 + QA 评测 + 工具准确率），输出报告
8. `eval/scripts/compare_baseline.py` 完善：Hybrid vs GraphRAG 全指标对比
9. **复现 P3/P6/P8 全部指标**：把三个 benchmark 脚本结果汇总成一份总报告 `eval/reports/final_report.md`（每个指标附：方法/数据集/结果/结论）
10. `observability/dashboard.py`：简单聚合（对话数/耗时分布/工具成功率/Trace 数），提供只读接口

**验收标准**：

```bash
uv run python eval/scripts/run_eval.py --all                      # 输出完整评测报告
cat eval/reports/final_report.md                                  # 五个指标全部有实测数据：
#   GraphRAG Recall@10 提升 ≥8%、可见工具数 -34.2%、Schema Token -32.6%、FC 准确率 ≥94%、并发 -77.6%
curl "http://localhost:8000/api/v1/traces/{session_id}"           # 完整 trace 树（agent/tool/retrieval 各层 span）
curl -X POST http://localhost:8000/api/v1/traces/replay -d '{"session_id":"..."}'   # replay 成功
uv run pytest tests/integration -q                                # 全绿
```

**面试要点**：评测集怎么构建的、baseline 怎么选的、指标口径是什么——这是面试官最可能深挖的地方，必须能脱口而出。

---

### P11 · 工程化收尾与面试就绪

**任务清单**：

1. **CI/CD**：`.github/workflows/ci.yml`（触发：PR → ruff → mypy → pytest unit/integration → coverage 上传）；`cd.yml`（main 合并 → 构建镜像 → 推 registry，k8s 部署段写注释说明，无需真实部署）
2. **Dockerfile**：multi-stage（builder 装依赖 → runtime 精简镜像 + 非 root 用户 + healthcheck）
3. **deploy/k8s/**：namespace/configmap/secrets.example/api-deployment/api-service/worker-deployment/hpa 七个清单文件（含资源配额与探针）
4. **README.md 完整化**：项目简介 + 架构图（复用设计文档 3.2）+ 快速开始（3 步起服务）+ 核心能力演示（文字 + 命令）+ 指标总览表 + 文档索引
5. **docs/ 完善**：architecture.md（复用设计文档）、api_reference.md（从 openapi.json 生成 + 手工补充示例）、skill_development.md（如何开发一个新 Skill）、deployment.md（docker-compose/k8s 两套部署说明）
6. **ADR 补齐**：把设计文档 D1-D7 落地为 `docs/adr/0001`~`0007`（含 P2/P8 新增的 0003/0004），格式：Context / Decision / Consequences
7. **demo 脚本**：`scripts/demo.py`（一键演示：上传文档 → 索引 → QA → 工具调用 → 多 Agent 任务，输出完整日志）
8. **最终质检**：全量门禁 + 覆盖率达标 + 全部测试通过
9. **面试叙事文档**：`docs/interview_story.md`（基于设计文档"四、面试核心叙事"扩写：每个指标的故事线 + 可能的追问与应答，含"诚实边界"——哪些是本地评测、无线上数据）

**验收标准**：

```bash
make lint && make test && make cov                               # 全绿，覆盖率 ≥60%（核心模块 ≥70%）
make up && make demo                                              # 一条命令起全栈并跑通演示
git log --oneline                                                 # 历史清晰、Conventional Commits
docker build -t knowflow:latest . && docker compose -f docker-compose.yml up   # 镜像可构建、服务可起
# 打开 README：快速开始 3 步可复现；指标表与 final_report.md 一致
# ADR 7 条齐全；interview_story.md 完成
```

---

## 五、全局验收清单（面试就绪总检查）

- [ ] `git clone` 后按 README 快速开始 3 步能起服务
- [ ] 上传 3 篇真实文档 → 索引 → 知识问答 → 流式回答（带引用）全链路可用
- [ ] Skill 启停、工具调用、执行域隔离可演示
- [ ] 复杂任务多 Agent 委派并发执行可演示，checkpoint 断点续跑可演示
- [ ] 跨会话长期记忆可演示
- [ ] `eval/reports/final_report.md` 五个指标全部有实测数据且与简历一致
- [ ] ruff / mypy / pytest / pre-commit 全绿,覆盖率达标
- [ ] CI 流水线配置完整（可展示截图）
- [ ] Dockerfile + deploy/k8s 清单齐全
- [ ] README / architecture.md / api_reference.md / skill_development.md / deployment.md / ADR×7 / interview_story.md 齐全
- [ ] Git 历史干净规范,CHANGELOG 有记录

---

## 六、风险与注意事项

| 风险 | 应对 |
|---|---|
| Milvus 本地部署重（内存 ≥8GB） | 若机器带不动,向量检索可暂用 PG `pgvector` 替代(Milvus 的 collection 接口封装好,切换只改 vector_store.py),面试讲清"本地资源受限的取舍" |
| Embedding/reranker 模型下载慢 | 首次 `uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"` 提前缓存;或先用 API embedding 跑通再切本地 |
| LLM API Key 成本 | 评测与演示用低价模型(deepseek-chat 等),大模型只用于实体抽取/汇总等必要处 |
| 指标达不到设计目标 | 指标是"目标值",验收以"有实测数据 + 趋势正确"为准(如 8% 提升,达到 5%+ 也如实报告);**严禁伪造数据**——面试被追问口径时诚实说明 |
| 时间不足 | 裁剪顺序:P9 最小实现 → P11 的 k8s 简化 → P8 只做单委派;但 P3/P6/P10 指标必须真实复现 |
