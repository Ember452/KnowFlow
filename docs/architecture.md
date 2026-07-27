# KnowFlow 系统架构

> 本文基于《项目设计文档》3.2 节与最终实现整理，描述各模块职责、依赖关系与关键设计决策。
> 架构决策（为什么这么选）见 [ADR 记录](adr/)。

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────┐
│                         客户端层                              │
│              Web / API Client / SSE Stream                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────┐
│                    API 网关层（FastAPI）                      │
│  路由 · 鉴权 · 租户隔离 · SSE 流式 · Trace 注入 · 限流        │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                  Agent 编排层（LangGraph）                    │
│  主 Agent ──task 委派──▶ 子 Agent（子线程隔离上下文）         │
│  checkpoint 父子关系 · 并发执行 · 可观测追踪 · 状态机         │
└──┬──────────┬──────────┬──────────┬──────────┬───────────────┘
   │          │          │          │          │
┌──▼──┐   ┌───▼───┐  ┌───▼────┐ ┌───▼────┐ ┌───▼────────┐
│Graph│   │工具治理│  │上下文  │ │沙盒    │ │流式+可观测 │
│RAG  │   │模块   │  │工程    │ │文件系统│ │+记忆       │
│检索 │   │       │  │模块    │ │模块    │ │模块        │
└──┬──┘   └───┬───┘  └───┬────┘ └───┬────┘ └───┬────────┘
   │          │          │          │          │
┌──▼──────────▼──────────▼──────────▼──────────▼───────────────┐
│                        存储层                                 │
│  Milvus(向量) · PostgreSQL(业务) · MinIO(文件)           │
│  Redis(会话+记忆)                                            │
└──────────────────────────────────────────────────────────────┘
```

## 2. 模块职责与关键设计

### 2.1 对话链路（services/chat_service.py）

单请求一个 ChatService 实例，链路：会话校验 → 消息入库 → 检索 → 记忆召回 → **多 Agent 编排 / 工具编排 / 直连** 三选一 → 落库。

- 同步 `chat()` 与流式 `stream_events()` 双入口
- 多 Agent 编排失败自动降级到直连链路（不阻塞对话）
- SSE 事件序列：`retrieval → [progress/tool_start/tool_end]* → token* → done`

### 2.2 混合检索（retrieval/）

| 组件 | 职责 |
|---|---|
| `pipeline.py` | 文档解析 → 分块（递归字符，默认 512/64）→ 向量/BM25 双写入库 |
| `hybrid_search.py` | 向量召回（Ollama embedding）+ BM25 双路 RRF 融合（k=60） |
| `reranker.py` | 本地交叉编码器二次精排 |
| `retriever.py` | 统一入口 + 检索缓存 |

### 2.3 工具治理（tools/）

- **四类执行域**：direct（恒可见）/ skill_only（按激活 Skill）/ subagent_only（按 Agent 角色）/ internal（永不可见）
- 可见工具计算 → JSON Schema 注入 → 工具调用循环（最多 5 轮）→ ToolCallRecord 落库
- Skill 体系：`skills/*/SKILL.md`（YAML frontmatter）→ SkillManager 运行时启停 → 依赖拓扑解析

### 2.4 Multi-Agent 编排（agents/）

LangGraph 状态机：`START → understand(规则意图) → plan(LLM 规划) ─┬─ delegate → execute(并发) ─┐`
                                                                   `└─ direct ───────────────────┤`
                                              `summarize(汇总/直答) ←──────────────────────────┘`

- 子 Agent 独立上下文（只看到自己的任务 + 共享预检索上下文）
- 并发执行：`asyncio.gather` + 超时（60s）+ 降级（单子失败不阻塞）
- checkpoint：LangGraph AsyncPostgresSaver 原生表，`thread_id = str(agent_run_id)`，lineage 沿 `parent_checkpoint_id` 回溯（ADR 0004）

### 2.5 上下文工程与记忆（context/ memory/）

- 预算分配（默认 32000 tokens）→ 超预算时按序：**摘要 → 卸载 → 截断**
- 卸载：超阈值内容（4000 tokens）写入沙盒文件，引用替换
- 记忆分层：Redis 短期（TTL 会话级）→ 重要性打分 + LLM 压缩 → PG 长期（向量召回）→ 每 5 轮自动沉淀

### 2.6 沙盒文件系统（sandbox/）

虚拟路径（`/workspace/x.json` ↔ MinIO key）+ 路径校验（拦截 `../`、绝对路径、跨会话）+ 配额（默认 100MB）+ TTL 清理。file_tools 直接读写沙盒。

### 2.7 可观测（observability/）

- `Tracer`：contextvars 传播 trace_id，嵌套 Span（agent_decision/tool_call/retrieval/memory_recall）
- `SpanCollector`：内存缓冲 + 批量落库（失败降级不阻塞主流程）
- `TraceStore`：嵌套树查询 / trace 时间序 / 聚合统计
- `Replayer`：checkpoint 恢复 + 时间序事件重放（不执行 LLM）
- `eval/`：数据集加载、指标计算（Recall@K/MRR/NDCG/要点命中/FC 准确率）、评测执行、报告渲染

### 2.8 异步索引（tasks/ + worker/）

Redis Stream 任务队列（index 流 + DLQ）→ 独立 worker 进程消费，重试 3 次后入死信队列。

## 3. 数据模型（PostgreSQL 19 张表）

- **文档**：documents / chunks / document_index
- **会话**：sessions / messages / turns
- **Agent**：agent_runs / task_delegations
- **工具**：tool_calls / skill_activations / tool_metrics
- **记忆**：memories / memory_sediment_logs
- **可观测**：trace_spans / trace_events
- **评测**：eval_datasets / eval_runs / eval_results

## 4. 关键链路时序

### 复杂任务（委派）

```
用户 → chat_service
  → retriever.retrieve（预检索）
  → MultiAgentOrchestrator.run
    → understand（规则分类 complex）
    → plan（LLM 规划子任务）
    → execute（创建子 run + delegations → asyncio.gather 并发 → 里程碑 checkpoint）
    → summarize（LLM 汇总子结果）
  → 答案落库 + SSE done
```

### 断点续跑

```
kill 进程 → 同一 thread_id + checkpoint_id 调 graph.ainvoke
  → LangGraph 从 checkpoint 恢复 channel 状态继续执行
  → task_delegations.checkpoint_id 精确定位委派里程碑
```

## 5. 架构决策索引

| ADR | 决策 |
|---|---|
| 0003 | checkpoint 存 PostgreSQL 而非 Redis |
| 0004 | 采用 LangGraph 原生 checkpoint（PostgresSaver） |
| 0005 | 依赖管理用 uv |
| 0006 | 流式用 SSE 不用 WebSocket |
| 0007 | 沙盒用 MinIO 不用本地文件系统 |
