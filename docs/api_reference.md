# KnowFlow API 参考

> 完整 OpenAPI 规范由 `uv run python scripts/gen_openapi.py` 生成（`openapi.json`，22 个路径）。
> 本文为分组说明 + 请求/响应示例。交互式文档：服务启动后访问 `http://localhost:8000/docs`。

## 1. 健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/healthz` | 存活探针（不检查依赖） |
| GET | `/api/v1/readyz` | 就绪探针（检查 PG/Redis/Milvus/MinIO） |

```bash
curl http://localhost:8000/api/v1/healthz
# {"status":"ok"}
```

## 2. 文档与索引

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/documents/upload` | 上传文档（pdf/docx/md/txt，≤50MB），入队索引 |
| GET | `/api/v1/documents` | 文档列表 |
| DELETE | `/api/v1/documents/{doc_id}` | 删除文档与索引 |
| POST | `/api/v1/documents/{doc_id}/reindex` | 重新索引 |

```bash
# 上传并触发异步索引（worker 消费后完成分块/embedding/向量与 BM25 入库）
curl -X POST http://localhost:8000/api/v1/documents/upload -F "file=@corpus.md"
# {"doc_id": 1, "status": "indexing", "message": "已入队"}
```

## 3. 知识检索

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/knowledge/search` | 知识库检索（混合检索全链路） |

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/search \
  -H "Content-Type: application/json" -d '{"query": "年假制度", "top_k": 5}'
# {"query": "年假制度", "chunks": [{"chunk_id": 3, "content": "入职满 1 年享有 5 天年假...", "score": 0.91}], "latency_ms": 132}
```

## 4. 对话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/chat` | 同步对话（检索+工具/多 Agent 编排，返回完整答案与引用） |
| POST | `/api/v1/chat/stream` | SSE 流式对话 |

```bash
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "员工年假制度是什么？"}'
# {"session_id": 1, "answer": "入职满 1 年享有 5 天年假，满 3 年享有 10 天...",
#  "citations": [{"chunk_id": 3, "content": "...", "score": 0.91, "source": "hybrid"}],
#  "tool_calls": [], "latency_ms": 892}
```

SSE 事件序列：`retrieval → [progress/tool_start/tool_end]* → token* → done`，心跳 `: ping` 每 15s：

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "对比产品 A/B/C 的价格并汇总"}'
# event: retrieval
# data: {"query": "...", "chunks": [...]}
# event: progress
# data: {"stage": "multi_agent", "delegated": true, "subtasks": ["t1", "t2", "t3"], "run_id": 1}
# event: token
# data: {"delta": "对比结果如下..."}
# event: done
# data: {"session_id": "1", "citations": [...], "latency_ms": 5230}
```

## 5. Multi-Agent 编排

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/agents/runs/{run_id}` | 父子 run 记录 + 委派链（状态机可见性） |

```bash
curl http://localhost:8000/api/v1/agents/runs/1
# {"run": {"id": 1, "agent_type": "main", "status": "completed", ...},
#  "children": [{"id": 2, "agent_type": "sub", "status": "completed", ...}, ...],
#  "delegations": [{"task": "查询产品 A 的价格", "status": "completed", "checkpoint_id": "..."}]}
```

## 6. Skill 管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/skills` | Skill 列表与启停状态 |
| PUT | `/api/v1/skills/{name}/toggle` | 启用/停用 Skill |

```bash
curl http://localhost:8000/api/v1/skills
# [{"name": "data_analysis", "enabled": true, "tools": ["calculator", "file_write_tool"]}, ...]
```

## 7. 记忆

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/memory/{user_id}` | 用户长期记忆列表 |
| DELETE | `/api/v1/memory/{user_id}/{memory_id}` | 删除单条记忆 |
| POST | `/api/v1/memory/{user_id}/sediment` | 手动触发记忆沉淀 |

## 8. 可观测（Trace / Replay / Dashboard）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/traces/{session_id}` | 嵌套 span 树 |
| GET | `/api/v1/traces/stats` | 近 N 小时聚合统计（对话数/耗时/工具成功率） |
| POST | `/api/v1/traces/replay` | checkpoint + trace 重放 |

```bash
curl http://localhost:8000/api/v1/traces/1
# {"session_id": 1, "roots": [{"span_type": "root", "children": [
#   {"span_type": "retrieval", "name": "hybrid_retrieve", "latency_ms": 132}, ...]}]}

curl -X POST http://localhost:8000/api/v1/traces/replay -d '{"session_id": 1}'
# {"session_id": 1, "run_id": 1, "checkpoint_id": "...",
#  "state": {"query": "...", "needs_delegation": true, ...},
#  "events": [{"span_type": "root", "name": "root", ...}, ...]}
```

## 9. 评测

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/eval/run` | 触发一次评测运行 |
| GET | `/api/v1/eval/runs/{run_id}` | 查询评测结果 |

## 10. 公共请求头

| Header | 说明 |
|---|---|
| `X-User-Id` | 用户标识（记忆隔离用），缺省 `anonymous` |

## 11. 错误格式

```json
{"code": "NOT_FOUND", "message": "会话不存在: session_id=999", "details": null}
```

常见状态码：`400` 校验失败 / `404` 资源不存在 / `422` 请求体非法 / `500` 内部错误。
