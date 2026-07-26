# M3 · API 层与异步索引 — 指标/验收测试文档

> 按 AGENTS.md 2.2 节要求编写。本测试需真实容器(PG/Milvus/Redis/MinIO)+ 真实 LLM/Embedding 模型,
> 当前 AI 环境无法完整执行, 交由用户实测后回填结果。单测可覆盖的部分已在 `tests/unit`、
> `tests/integration` 自动验证(257 passed), 本文档仅记录需运行环境的端到端验收。

---

## 一、前置条件

### 1.1 依赖服务

```bash
docker compose up -d
docker compose ps          # postgres / milvus / redis / minio 均 healthy
```

### 1.2 环境变量

`.env` 已填入真实值:

- `KNOWFLOW_LLM_API_KEY` / `KNOWFLOW_LLM_BASE_URL` / `KNOWFLOW_LLM_MODEL`(DeepSeek 等)
- `KNOWFLOW_EMBEDDING_MODEL=BAAI/bge-m3`(首次需本地缓存模型)
- `KNOWFLOW_RERANKER_MODEL=BAAI/bge-reranker-v2-m3`(首次需本地缓存)
- PG / Redis / Milvus / MinIO 连接参数与 docker-compose 一致

### 1.3 初始化

```bash
uv run python scripts/init_db.py          # 建库 + 迁移
uv run python scripts/init_milvus.py      # 建 Milvus collection
uv run ruff check src/ && uv run mypy src/ worker/   # 0 errors
uv run pytest tests/unit tests/integration -q        # 全绿(257 passed)
```

### 1.4 模型缓存(首次)

```bash
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-v2-m3')"
```

---

## 二、启动步骤

```bash
# 终端 1: API
uv run uvicorn knowflow.main:app --reload --port 8000

# 终端 2: Worker
uv run python -m worker.main

# 确认服务就绪
curl http://localhost:8000/api/v1/healthz
curl http://localhost:8000/api/v1/readyz     # 期望 deps 全 ok
```

---

## 三、测试用例与结果记录

### 用例 1: 健康检查与就绪探针

**步骤**:
```bash
curl -s http://localhost:8000/api/v1/healthz | jq .
curl -s http://localhost:8000/api/v1/readyz | jq .
```

**预期**:
- `/healthz` 返回 `{"code":"ok","data":{"status":"ok"}}`
- `/readyz` 返回 `deps` 中 postgres/redis/milvus/minio 均 `ok`, 顶层 `status=ok`

| 项 | 预期 | 实测 |
|---|---|---|
| /healthz status | ok | ______ |
| /readyz postgres | ok | ______ |
| /readyz redis | ok | ______ |
| /readyz milvus | ok | ______ |
| /readyz minio | ok | ______ |

---

### 用例 2: 文档上传(真实 PDF)

**步骤**:
```bash
curl -s -X POST -F "file=@docs/KnowFlow-项目设计文档.pdf" \
  -H "X-User-Id: tester" \
  http://localhost:8000/api/v1/documents/upload | jq .
```

**预期**: 返回 `doc_id`, `status="pending"`, `duplicated=false`。

| 项 | 预期 | 实测 |
|---|---|---|
| HTTP 状态 | 200 | ______ |
| status | pending | ______ |
| doc_id | > 0 | ______ |

---

### 用例 3: 异步索引状态流转

**步骤**:
```bash
# 上传后立即轮询列表, 观察状态
watch -n 1 'curl -s -H "X-User-Id: tester" http://localhost:8000/api/v1/documents | jq .data.items[0].status'
```

**预期**: 状态序列 `pending → indexing → ready`(Worker 消费后)。Worker 日志可见
`index_task.done` 与 chunk/entity 计数。

| 项 | 预期 | 实测 |
|---|---|---|
| 终态 | ready | ______ |
| chunk 数 | > 0 | ______ |
| Milvus 有向量 | 是(查询 collection) | ______ |
| PG chunks/entities 有数据 | 是 | ______ |

**验证 Milvus/PG 落数**:
```bash
# Milvus(通过 pymilvus 查询 collection 行数)
uv run python -c "from pymilvus import MilvusClient, connections, Collection; from knowflow.core.config import get_settings; s=get_settings(); c=Collection(s.milvus_collection); c.load(); print('rows:', c.num_entities)"

# PG chunks
docker compose exec postgres psql -U knowflow -d knowflow -c "select count(*) from chunks; select count(*) from entities;"
```

---

### 用例 4: 知识检索

**步骤**:
```bash
curl -s -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Content-Type: application/json" \
  -d '{"query":"报销流程是什么","top_k":5}' | jq .
```

**预期**: 返回 `chunks` 非空, 含 `content`/`score`/`source`, `latency_ms` 有值, `cache_hit=false`。
第二次同 query 且同检索参数(top_k/with_expand/with_rerank)`cache_hit=true`(Redis 缓存命中)。
文档索引/删除成功后缓存自动失效(用例 5 后重查同 query 应 `cache_hit=false`)。

| 项 | 预期 | 实测 |
|---|---|---|
| HTTP 状态 | 200 | ______ |
| chunks 数 | > 0 | ______ |
| content 非空 | 是 | ______ |
| 二次 cache_hit | true | ______ |
| 文档变更后重查 cache_hit | false | ______ |

---

### 用例 5: 重建索引 / 删除

**步骤**:
```bash
# reindex
curl -s -X POST http://localhost:8000/api/v1/documents/{doc_id}/reindex | jq .
# delete
curl -s -X DELETE http://localhost:8000/api/v1/documents/{doc_id} | jq .
```

**预期**: reindex 后状态回 `pending` 并重新走 indexing→ready; delete 后列表不再包含, Milvus/BM25 对应数据已清理。

| 项 | 预期 | 实测 |
|---|---|---|
| reindex 后终态 | ready | ______ |
| delete deleted | true | ______ |
| 删除后列表无该 doc | 是 | ______ |

---

### 用例 6: OpenAPI 文档生成

**步骤**:
```bash
uv run python scripts/gen_openapi.py
```

**预期**: 生成 `openapi.json`, 路径数 ≥ 17(含 chat/document/knowledge/health/agent/skill/memory/trace/eval)。

| 项 | 预期 | 实测 |
|---|---|---|
| 生成成功 | 是 | ______ |
| 路径数 | ≥ 17 | ______ |

---

### 用例 7: 集成测试(已自动化, 真实容器下复跑)

**步骤**:
```bash
uv run pytest tests/integration/test_index_pipeline.py -q
```

**预期**: 全绿(基于 SQLite+fake 的全链路: 上传→入队→消费→ready)。

| 项 | 预期 | 实测 |
|---|---|---|
| 测试结果 | passed | ______ |

---

## 四、已知限制与说明

1. **BM25 进程内增量不跨进程同步**: BM25Store 为进程内内存索引, API 与 Worker 启动时各自
   从 chunks 表全量加载(重启后恢复一致); 但索引新文档后仅更新所在进程的实例, 另一进程重启前
   看不到增量。知识检索在多进程下主要由向量路(Milvus, 外部共享)召回, BM25 贡献受限 —— 属
   M2 内存索引设计的取舍, 不影响 M3 接口正确性。
2. **chat/agent/skill/memory/trace/eval 端点**: M3 仅占位返回 501, 主流程在 P5-P10 对应里程碑实现。
3. **限流**: Redis 不可用时降级放行(不阻塞业务); 健康检查路径(/healthz、/readyz、/health)不限流。
4. 秒传去重基于内容 sha256, 同内容重复上传返回 `duplicated=true` 不重复索引。

---

## 五、验收清单

- [ ] 用例 1-7 全部预期达成
- [ ] 门禁全绿(ruff / mypy / pytest unit+integration)
- [ ] 真实文档上传 → 索引 → 检索 全链路可用
- [ ] openapi.json 生成且路径数 ≥ 17
