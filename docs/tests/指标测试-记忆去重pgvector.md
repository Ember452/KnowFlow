# 记忆去重 pgvector 改造 — 指标/验收测试文档

> 按 AGENTS.md 2.2 节要求编写。去重的**决策路由 / 二次校验 / SQL 编译**已在
> `tests/unit/memory/test_dedup_pgvector.py` 自动验证(SQLite 离线可测);
> 数据库向量 top-N 检索(依赖真实 PostgreSQL + pgvector 扩展)需真实环境,
> 交由用户实测后回填结果表。

---

## 一、前置条件

### 1.1 依赖服务

- 真实 PostgreSQL(**需支持 pgvector 扩展**, 镜像带 `vector` 扩展或可创建)。
- 首次部署时 `.env` 的 `KNOWFLOW_POSTGRES_*` 指向该 PG。

### 1.2 环境变量

```bash
KNOWFLOW_POSTGRES_HOST/PORT/USER/PASSWORD/DB   # 指向真实 PG
KNOWFLOW_EMBEDDING_PROVIDER=api                 # 或 local(维度需为 1024)
KNOWFLOW_EMBEDDING_MODEL=text-embedding-v4       # 默认 1024 维, 与 VECTOR(1024) 对齐
# 去重参数(默认即可):
#   KNOWFLOW_MEMORY_DEDUP_THRESHOLD=0.9
#   KNOWFLOW_MEMORY_DEDUP_CANDIDATE_COUNT=10
```

> 注意: 向量列固定 `vector(1024)`, embedding 模型输出维度必须为 1024;
> 维度不符时 SQL 路径会报错并自动降级 Python 全量扫描(见用例 5)。

### 1.3 迁移与门禁

```bash
uv run python scripts/init_db.py                 # 应用迁移 0004(建扩展/向量列/HNSW 索引)
uv run ruff check src/ tests/ scripts/ worker/   # 0 errors(本次新增文件)
uv run mypy src/ worker/                         # 0 errors
uv run pytest tests/unit -q                      # 全绿
```

迁移 0004 说明:
- `CREATE EXTENSION IF NOT EXISTS vector`(无扩展创建权限时迁移自动跳过,
  应用降级 Python 去重, 不阻塞部署);
- `long_term_memories` 增加 `embedding_vec vector(1024)` 列;
- HNSW 余弦索引 `idx_memories_user_vec`(近似最近邻检索)。

### 1.4 存量数据回填(可选但强烈建议)

```bash
uv run python scripts/backfill_memory_vectors.py            # 把 embedding(LargeBinary) 回填到 embedding_vec
uv run python scripts/backfill_memory_vectors.py --batch 1000
```

> 回填前, 含存量数据的用户去重自动降级 Python 全量扫描(行为与旧版一致, 功能不受影响);
> 回填后 SQL top-N 路径对全部用户生效。

---

## 二、启动步骤

```bash
uv run uvicorn knowflow.main:app --reload --port 8000
curl http://localhost:8000/api/v1/readyz        # deps 全 ok
```

---

## 三、测试用例与结果记录

### 用例 1: 迁移与能力探测

```bash
# 1) 确认扩展/列/索引存在
psql "$KNOWFLOW_POSTGRES_DSN" -c "SELECT extname FROM pg_extension WHERE extname='vector'"
psql "$KNOWFLOW_POSTGRES_DSN" -c "\d long_term_memories"        # 含 embedding_vec vector(1024)
psql "$KNOWFLOW_POSTGRES_DSN" -c "\di idx_memories_user_vec"    # hnsw 索引存在
# 2) 服务启动日志无 pgvector_probe_failed / dedup_vector_query_failed 告警
```

**预期**: 扩展存在、列存在、索引存在; 日志无向量路径告警。

### 用例 2: 写入去重走 SQL top-N(不拉全量)

对同一用户连续写入 3 条高度相似记忆 + 2 条不同主题, 观察 PG 查询与结果:

```bash
# 先清空测试用户记忆
curl -s http://localhost:8000/api/v1/memory/dedup_test
# 手动沉淀 3 次相似偏好(内容略有差异), 再沉淀 2 条不同主题(通过对话轮询触发沉淀或直接调 sediment 端点)
```

**预期**: 相似记忆仅保留 1 条(内容为最新表述, importance 取 max); 不同主题各自独立;
存储条数 = 3(1 相似 + 2 独立)。可用 `pg_stat_statements`/`EXPLAIN ANALYZE` 抽查
写入去重产生的 SQL 为带 `embedding_vec <=> ...` 的 top-10 检索, 而非全表拉取。

```sql
EXPLAIN ANALYZE
SELECT * FROM long_term_memories
WHERE user_id = 'dedup_test' AND embedding_vec IS NOT NULL
ORDER BY embedding_vec <=> '[0.1,0.2,...]'  -- 真实查询向量
LIMIT 10;
```

**预期**: 走 HNSW 索引扫描(或至少非全表拉取后内存算相似度)。

### 用例 3: 二次校验精度(0.9 阈值语义不变)

- 近似表述(高字符重叠)判定重复 → 覆盖更新, 不新增;
- 不同主题判定不重复 → 各自独立;
- 仅差标点的重复表述(无 embedding 场景)走文本兜底仍合并。

**预期**: 与改造前去重行为完全一致(阈值 0.9 语义不变)。

### 用例 4: 降级路径(不回填存量时)

1. 造一条存量记忆: 手动把某行 `embedding_vec` 置空(`UPDATE ... SET embedding_vec=NULL`);
2. 再写入重复内容。

**预期**: 该用户去重仍生效(自动降级 Python 全量扫描), 日志出现
`memory.dedup_vector_query_failed` 或正常降级路径日志, 功能不受影响。

### 用例 5: 维度不符自动降级

将某用户 `embedding_vec` 写一条非 1024 维向量, 再写入新记忆。

**预期**: 不报错、不阻塞写入; SQL 路径失败自动降级 Python 全量扫描, 去重仍正确。

### 用例 6: 回归(召回/冲突/列表不受影响)

```bash
uv run pytest tests/unit -q
# 手工: 对话中能召回已沉淀记忆; GET /memory/{uid} 列表正常; 冲突检测正常
```

**预期**: 全量单测全绿; 召回、列表、冲突检测与改造前一致(本次仅改写入去重路径)。

---

## 四、结果记录表(待用户实测后填写)

| 用例 | 步骤 | 实测结果 | 通过 |
|---|---|---|---|
| 1 | 扩展/列/索引 + 无告警日志 | | |
| 2 | 相似去重 + top-N SQL 生效 | | |
| 3 | 0.9 阈值语义不变 | | |
| 4 | 存量未回填降级 Python | | |
| 5 | 维度不符降级不阻塞 | | |
| 6 | 全量单测 + 回归 | | |

> 实测完成后把本表回填给 AI, 由 AI 将结果写入对应报告并保留本文件作为证据。
