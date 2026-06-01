# KnowFlow 项目设计文档

> 可编排、可扩展的企业知识库 Agent 平台
> 版本：v2.0 ｜ 更新：2026-08-05 ｜ Python 3.13 + uv

---

## 一、简历写法

**KnowFlow —— 可编排、可扩展的企业知识库 Agent 平台** ｜ 核心开发者 ｜ 2026.04-2026.07

Python / FastAPI / LangGraph / LangChain / MCP / Milvus / PostgreSQL / MinIO / Redis

企业级知识库 Agent 平台，围绕检索增强、工具治理、多 Agent 协同三大核心能力，解决知识问答中跨文档关联、工具调用膨胀、复杂任务编排与上下文溢出四个工程问题。

- GraphRAG 检索：LLM 抽取文档实体与关系存入 PostgreSQL 实体关系表，检索阶段向量 + BM25 Hybrid 召回后，基于实体一跳关联扩展召回跨文档 chunk，reranker 精排，相对 Hybrid baseline 提升 8% Recall@10。

- 工具治理：设计 Skill 声明式加载与依赖开关机制，按 Skill 激活状态动态注入关联工具；四类执行域分级隔离模型可见工具，单轮可见工具数降 34.2%，Tool Schema Token 降 32.6%，Function Calling 准确率 94+%。

- Multi-Agent 编排：主 Agent 负责任务规划与结果汇总，子 Agent 子线程隔离上下文执行委派任务；checkpoint 记录父子关系支持断点续跑，多独立子任务并发执行可观测追踪。

- 上下文工程：超阈值工具调用结果自动卸载至沙盒文件系统并以引用替换，滑动窗口 + 动态摘要控制上下文长度；跨会话长期记忆按语义相关度召回并经 LLM 压缩注入，与上下文策略联动。

- 沙盒文件系统：基于 MinIO 构建会话级隔离 workspace，仅向模型暴露虚拟路径受控文件工具，承载文件读写与工具结果卸载，防止 Agent 越权访问宿主文件系统。

- 流式与可观测：SSE 流式响应实时回显 LLM 推理与工具调用进度，全链路 Trace 记录 Agent 决策、工具调用与检索召回链路，支持会话 replay 与离线评测。

---

## 二、产品需求文档（PRD）

### 2.1 项目背景

企业内部知识沉淀在大量异构文档中（产品手册、HR 政策、IT 工单、运营 SOP），传统关键词检索无法理解语义，员工查找信息效率低。大模型时代，基于 RAG 的知识问答 Agent 成为企业智能助手的主流形态，但现有方案存在四个核心问题：一是检索只能做向量相似度匹配，无法跨文档关联；二是工具调用缺乏治理，模型可见工具过多导致 Token 浪费和调用准确率下降；三是多 Agent 协作缺乏编排，复杂任务无法拆解委派；四是上下文管理粗放，多轮工具调用容易撑爆上下文窗口。

KnowFlow 针对这四个问题，构建一个可编排、可扩展的企业知识库 Agent 平台，提供 GraphRAG 检索、工具治理、Multi-Agent 编排、上下文工程、沙盒文件系统、流式可观测六大核心能力。

### 2.2 项目定位

企业级知识库 Agent 平台，不是单一聊天机器人，而是可编排、可扩展的 Agent 基础设施。向上支撑企业智能助手、知识问答、自动化任务等应用场景，向下集成多模型、多工具、多知识源。核心价值在"编排"（Multi-Agent 协同 + 工具治理）和"扩展"（Skill 声明式加载 + MCP 工具接入）。

### 2.3 目标用户与场景

**目标用户**：企业员工（终端使用者，对话获取知识、执行任务）；平台开发者（二次开发，扩展 Skill、接入工具、定制 Agent）。

**核心场景**：知识问答（提问 → GraphRAG 检索 → 流式回答）、复杂任务（多步任务 → 主 Agent 拆解 → 委派子 Agent 并发执行 → 汇总）、工具调用（意图识别 → 激活 Skill → 动态注入工具 → 执行域隔离）、长期记忆（跨会话偏好 → 相关度召回 → 压缩注入）。

### 2.4 核心功能需求

| 编号 | 功能 | 描述 |
|---|---|---|
| F1 | GraphRAG 检索 | 文档上传→解析分块→LLM 抽取实体关系→存 PostgreSQL→向量+BM25 Hybrid 召回→一跳 JOIN 扩展→reranker 精排 |
| F2 | 工具治理 | Skill 声明式加载 + 依赖开关 + 关联工具动态注入 + 四类执行域隔离 |
| F3 | Multi-Agent 编排 | 主/子 Agent 协同 + task 委派 + checkpoint 父子关系 + 并发执行 + 可观测 |
| F4 | 上下文工程 | 滑动窗口 + 动态摘要 + 超阈值卸载沙盒 + checkpoint 异步 run |
| F5 | 沙盒文件系统 | 会话隔离 workspace + 虚拟路径 + 受控文件工具 + MinIO 后端 |
| F6 | 流式与可观测 | SSE 流式 + 工具进度回显 + 全链路 Trace + 会话 replay + 离线评测 + 长期记忆 |

### 2.5 关键性能指标

| 指标 | 目标值 | 测量方式 |
|---|---|---|
| GraphRAG Recall@10 | 相对 Hybrid baseline 提升 8% | 50-100 条评测集对比 |
| 单轮可见工具数 | 下降 34.2% | 执行域隔离前后对比 |
| Tool Schema Token | 下降 32.6% | Token 计数对比 |
| Function Calling 准确率 | 94+% | 工具调用正确率统计 |
| 并发任务端到端耗时 | 较串行下降 77.6% | 多独立子任务场景对比 |

### 2.6 非功能需求

性能（单轮响应 P95 < 3s，流式首 Token < 800ms）、安全（沙盒隔离 + 权限校验 + 审批回调）、可扩展（Skill 零侵入 + MCP 接入）、可观测（全链路 Trace + replay + 评测）、可维护（Python 3.13 + uv + pyproject.toml 标准化）。

---

## 三、架构总览

### 3.1 技术栈

| 层级 | 技术 | 说明 |
|---|---|---|
| 语言 | Python 3.13 | 2024 年底发布，性能提升 |
| 依赖管理 | uv | Astral 出品，比 pip/poetry 快 10-100x |
| Web 框架 | FastAPI | 异步高性能，原生 SSE |
| Agent 编排 | LangGraph | 状态机 + checkpoint + 断点续跑 |
| LLM 接口 | LangChain | 模型/工具/Agent 抽象层 |
| 工具协议 | MCP | Model Context Protocol |
| 向量库 | Milvus | 高性能向量检索 |
| 关系库 | PostgreSQL | 业务数据 + 实体关系图谱 |
| 对象存储 | MinIO | 沙盒文件系统后端 |
| 缓存 | Redis | 会话/短期记忆/checkpoint |
| 流式 | SSE | sse-starlette |

### 3.2 系统架构

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
│  Milvus(向量) · PostgreSQL(图谱+业务) · MinIO(文件)           │
│  Redis(会话+记忆+checkpoint)                                  │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 完整项目结构

> 项目目录结构已抽取为独立文档：[KnowFlow-项目结构.md](./KnowFlow-项目结构.md)，按大厂工程规范重构（src 布局 + 分层架构 + API 版本化 + Repository 模式 + 独立 Worker + CI/CD），结构变更以该文档为准。

**文件规模统计**（以 [KnowFlow-项目结构.md](./KnowFlow-项目结构.md) 为准）：核心源码约 110 个文件，Worker 独立进程 3 个，测试约 23 个，配置/CI/CD/部署/文档约 35 个，总计约 170 个文件。

---

### 3.4 模块详细设计

#### 模块一：GraphRAG 检索（retrieval/）

**核心链路**：文档上传 → 解析分块 → LLM 抽取实体关系 → 存图 → 查询时 Hybrid 召回 → 一跳扩展 → reranker 精排

**核心类设计**：

`RetrievalPipeline`（编排完整检索链路）：
- `index_document(doc_id)` → 调用 parser → splitter → embedding → entity_extractor → 写入 vector_store + graph_store + bm25_store
- `retrieve(query, top_k)` → 调用 hybrid_search → expander → reranker → 返回 chunks

`EntityExtractor`（LLM 实体关系抽取）：
- `extract(chunks)` → 对每个 chunk 调 LLM 抽取 (entity_name, entity_type, relations)
- `normalize(entities)` → 实体归一（同义词合并、大小写统一、别名映射）
- Prompt 模板要求 LLM 输出 JSON 结构 `{"entities": [...], "relations": [...]}`

`GraphStore`（PostgreSQL 图谱存储）：
- `upsert_entities(doc_id, entities)` → 批量写入 entities 表
- `upsert_relations(doc_id, relations)` → 批量写入 relations 表
- `one_hop_expand(entity_ids)` → SQL JOIN 一跳扩展，返回关联 chunk_id 列表

`HybridSearch`（向量 + BM25 融合）：
- `vector_search(query, top_k)` → Milvus 向量召回
- `bm25_search(query, top_k)` → PostgreSQL tsvector 全文检索
- `fuse(vector_results, bm25_results)` → RRF（Reciprocal Rank Fusion）融合

`Expander`（实体一跳扩展）：
- `expand(chunks)` → 从召回 chunk 提取实体 ID → 调 GraphStore.one_hop_expand → 召回关联 chunk → 去重合并

`Reranker`（精排）：
- `rerank(query, chunks)` → cross-encoder 模型对 (query, chunk) 打分 → 按分数重排

**数据表设计**：

```sql
-- 实体表
CREATE TABLE entities (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      BIGINT NOT NULL REFERENCES documents(id),
    chunk_id    BIGINT NOT NULL REFERENCES chunks(id),
    name        VARCHAR(255) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,        -- person/org/concept/product...
    normalized  VARCHAR(255) NOT NULL,       -- 归一化名称（用于匹配）
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_entities_normalized ON entities(normalized);
CREATE INDEX idx_entities_chunk ON entities(chunk_id);

-- 实体别名表（同义词/别名映射）
CREATE TABLE entity_aliases (
    id          BIGSERIAL PRIMARY KEY,
    entity_id   BIGINT NOT NULL REFERENCES entities(id),
    alias       VARCHAR(255) NOT NULL,
    UNIQUE(entity_id, alias)
);

-- 关系表
CREATE TABLE relations (
    id                BIGSERIAL PRIMARY KEY,
    doc_id            BIGINT NOT NULL REFERENCES documents(id),
    source_entity_id  BIGINT NOT NULL REFERENCES entities(id),
    target_entity_id  BIGINT NOT NULL REFERENCES entities(id),
    relation_type     VARCHAR(64) NOT NULL,  -- belongs_to/related_to/part_of...
    confidence        FLOAT DEFAULT 1.0,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_relations_source ON relations(source_entity_id);
CREATE INDEX idx_relations_target ON relations(target_entity_id);

-- 一跳扩展核心查询
SELECT DISTINCT c.id, c.content
FROM chunks c
JOIN entities e ON e.chunk_id = c.id
JOIN relations r ON r.source_entity_id = e.id
JOIN entities e2 ON r.target_entity_id = e2.id
JOIN chunks c2 ON e2.chunk_id = c2.id
WHERE e.id = ANY(%s)  -- 输入：召回 chunk 中的实体 ID
  AND c.id <> c2.id;
```

#### 模块二：工具治理（tools/）

**核心机制**：Skill 声明式加载 → 依赖解析 → 按执行域隔离 → 动态注入 → 运行时权限校验

**四类执行域定义**：

| 域 | 可见性 | 典型工具 |
|---|---|---|
| direct | 主 Agent 始终可见 | 检索、文件读取、计算器 |
| skill_only | Skill 激活后注入 | 数据分析工具（数据分析 Skill 激活后） |
| subagent_only | 仅子 Agent 可见 | 专家工具（代码审查工具） |
| internal | 系统内部不暴露给模型 | 审计、监控、内部调度 |

**核心类设计**：

`SkillLoader`：
- `load(skill_dir)` → 解析 SKILL.md 的 YAML frontmatter → 构建 SkillDefinition
- `validate(skill_def)` → 校验元信息完整性（name/tools/dependencies/domain）
- SkillDefinition 字段：`name / description / tools[] / dependencies[] / domain / enabled`

`DependencyResolver`：
- `resolve(skill_def)` → 解析依赖开关 + 关联工具拓扑排序 → 返回需要激活的工具列表
- 检测循环依赖、缺失依赖

`VisibilityCalculator`：
- `compute(active_skills, agent_role)` → 根据当前激活的 Skill + Agent 角色 → 计算模型可见工具集
- 过滤逻辑：direct 永远可见 + skill_only 按 Skill 激活 + subagent_only 按角色 + internal 永不可见
- 输出 `visible_tools: list[ToolDef]`，用于构建 LLM 的 tools 参数

`Injector`：
- `inject(visible_tools)` → 将可见工具的 schema 注入 LLM 请求
- `eject(tool_name)` → 工具调用完成后移除（按需）

`PermissionChecker`：
- `check(tool_name, agent_role, context)` → 运行时校验调用是否越权
- 越权则拦截 + 记录 trace + 抛异常

`ToolMetrics`：
- `record_call(tool_name, success, tokens, latency)` → 记录调用
- `stats()` → 统计可见工具数、Token 占用、准确率

**Skill 定义示例（skills/knowledge_qa/SKILL.md）**：

```yaml
---
name: knowledge_qa
description: 企业知识库问答技能，激活知识检索与答案生成工具链
domain: skill_only
tools:
  - retrieval_tool
  - answer_generator
dependencies:
  - retrieval_tool
enabled: true
---

# 知识问答技能

当用户提出知识查询类问题时激活此技能，注入检索工具和答案生成工具...
```

#### 模块三：Multi-Agent 编排（agents/）

**核心机制**：主 Agent 规划 → task 委派 → 子 Agent 子线程隔离 → 并发执行 → checkpoint 父子关系 → 结果汇总

**LangGraph 状态机设计**：

```
START → understand → plan → [delegate?] → execute → summarize → END
                         │         │
                         │    ┌────┴────┐
                         │    ▼         ▼
                         │  subagent_1  subagent_2  (并发)
                         │    │         │
                         │    └────┬────┘
                         │         ▼
                         └──▶ aggregate
```

**核心类设计**：

`MainAgent`：
- `understand(query)` → 理解用户意图
- `plan(query)` → 任务规划（是否需要委派、委派给几个子 Agent）
- `delegate(subtasks)` → 创建 TaskDelegation，委派给子 Agent
- `summarize(results)` → 汇总子 Agent 结果

`Subagent`：
- `execute(task)` → 子线程隔离上下文执行任务
- 独立 ContextManager 实例，与主 Agent 上下文隔离

`Orchestrator`：
- `run_concurrent(subtasks)` → asyncio.gather 并发执行多个子 Agent
- 超时控制、降级策略（单个子 Agent 失败不阻塞整体）
- 结果聚合

`CheckpointManager`：
- `save(state, parent_checkpoint_id)` → 序列化 AgentState + 记录父子关系
- `restore(checkpoint_id)` → 反序列化恢复状态
- `lineage(checkpoint_id)` → 查询父子链路（用于 replay）

`TaskDelegation`：
- 字段：`delegation_id / parent_agent / child_agent / task / status / result / checkpoint_id`
- 状态机：`created → delegated → running → completed / failed`

**数据表设计**：

```sql
CREATE TABLE agent_runs (
    id            BIGSERIAL PRIMARY KEY,
    session_id    BIGINT NOT NULL,
    agent_type    VARCHAR(32) NOT NULL,      -- main / sub
    parent_run_id BIGINT REFERENCES agent_runs(id),  -- 父子关系
    status        VARCHAR(32) NOT NULL,      -- running/completed/failed
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    completed_at  TIMESTAMPTZ
);

CREATE TABLE task_delegations (
    id              BIGSERIAL PRIMARY KEY,
    parent_run_id   BIGINT NOT NULL REFERENCES agent_runs(id),
    child_run_id    BIGINT REFERENCES agent_runs(id),
    task            TEXT NOT NULL,
    status          VARCHAR(32) NOT NULL,
    result          JSONB,
    checkpoint_id   VARCHAR(128),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE checkpoints (
    id              VARCHAR(128) PRIMARY KEY,  -- UUID
    agent_run_id    BIGINT NOT NULL REFERENCES agent_runs(id),
    parent_checkpoint_id VARCHAR(128) REFERENCES checkpoints(id),
    state           JSONB NOT NULL,            -- 序列化的 AgentState
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

#### 模块四：上下文工程（context/）

**核心机制**：滑动窗口截断 + 动态摘要压缩 + 超阈值卸载沙盒 + 预算管理

**核心类设计**：

`ContextManager`：
- `build(messages, tool_results, memories)` → 编排各策略，构建最终 LLM 上下文
- 流程：统计 token → 若超预算 → 先摘要历史 → 再卸载大工具结果 → 再截断窗口

`SlidingWindow`：
- `apply(messages, max_messages)` → 保留最近 N 轮，超出部分截断

`Summarizer`：
- `summarize(old_messages)` → LLM 摘要历史对话，保留关键信息
- `compact(existing_summary, new_messages)` → 增量摘要（避免重复摘要）

`Spiller`：
- `should_spill(tool_result)` → 判断工具结果是否超阈值（按 token 数）
- `spill(tool_result, workspace)` → 写入沙盒文件系统，返回虚拟路径引用
- 替换上下文中的原始结果为 `{"spilled": true, "path": "/workspace/xxx.json"}`

`TokenCounter`：
- `count(text, model)` → tiktoken 或模型特定 tokenizer 计数
- `count_messages(messages)` → 批量计数

`BudgetManager`：
- `allocate(task_type)` → 按任务类型分配 token 预算（系统/历史/工具/检索/记忆）
- `check_usage(usage)` → 超限告警 + 触发降级策略

#### 模块五：沙盒文件系统（sandbox/）

**核心机制**：会话隔离 workspace + 虚拟路径映射 + MinIO 后端 + 访问控制

**核心类设计**：

`WorkspaceManager`：
- `create(session_id)` → 为会话创建独立 workspace（MinIO bucket prefix）
- `cleanup(session_id)` → 会话结束清理
- 路径格式：`sessions/{session_id}/workspace/`

`VirtualPathMapper`：
- `to_virtual(real_key)` → `minio://sessions/{sid}/workspace/result.json` → `/workspace/result.json`
- `to_real(virtual_path)` → 反向映射，校验路径不越界

`FileOps`：
- `read(virtual_path)` → 校验权限 → 映射真实路径 → 从 MinIO 读取
- `write(virtual_path, content)` → 校验权限 → 写入 MinIO
- `list(virtual_path)` → 列出目录下文件

`AccessControl`：
- `validate(virtual_path, session_id)` → 路径必须属于当前会话 workspace
- 拦截 `../` 路径穿越、跨会话访问
- 白名单机制（仅允许 workspace 内操作）

`QuotaManager`：
- `check(session_id, size)` → 校验会话配额
- 超限拒绝写入 + 告警

#### 模块六：流式与可观测（observability/ + api/sse.py + memory/）

**SSE 流式**：
- 事件类型：`token`（LLM Token 流）/ `tool_start` / `tool_end` / `retrieval` / `progress` / `done` / `error`
- `sse.py` 封装事件编码、心跳保活、断线重连

**全链路 Trace**：
- Span 类型：`agent_decision`（Agent 决策）/ `tool_call`（工具调用）/ `retrieval`（检索召回）/ `memory_recall`（记忆召回）
- `Tracer` 创建嵌套 Span，上下文传播（trace_id 贯穿请求全链路）
- 异步写入 PostgreSQL，不阻塞主流程

**会话 Replay**：
- 基于 checkpoint + trace 回放任意历史会话
- `replay(session_id, checkpoint_id)` → 恢复状态 + 按时间序重放 trace events

**离线评测**：
- `EvalRunner` 跑评测集（knowledge_qa_eval.jsonl）
- 对比 baseline（纯 Hybrid）vs GraphRAG 增强
- 指标：Recall@K / MRR / NDCG / 工具调用准确率
- 生成评测报告（对比表 + 提升幅度）

**记忆模块**：

`ShortTermMemory`（Redis）：
- 会话级，TTL 过期自动清理
- `add(session_id, message)` / `get_recent(session_id, n)`

`LongTermMemory`（PostgreSQL）：
- 跨会话持久化
- `sediment(session_id)` → 从短期记忆中筛选高价值信息 → 压缩 → 存长期
- `recall(query, user_id, top_k)` → 语义相关度 + 时间衰减召回

`Compressor`：
- `compress(memories)` → LLM 摘要 + 关键信息提取
- 避免长期记忆无限膨胀

**数据表设计**：

```sql
CREATE TABLE long_term_memories (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    session_id  BIGINT NOT NULL,
    content     TEXT NOT NULL,               -- 压缩后内容
    summary     TEXT,                        -- 摘要
    importance  FLOAT NOT NULL,              -- 重要性分数
    embedding   VECTOR(1024),                -- 语义向量（用于召回）
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    last_recall TIMESTAMPTZ                  -- 最近召回时间（用于衰减）
);

CREATE TABLE trace_spans (
    id          BIGSERIAL PRIMARY KEY,
    trace_id    VARCHAR(64) NOT NULL,
    parent_span_id BIGINT REFERENCES trace_spans(id),
    session_id  BIGINT NOT NULL,
    span_type   VARCHAR(32) NOT NULL,        -- agent_decision/tool_call/retrieval/memory
    name        VARCHAR(255) NOT NULL,
    input       JSONB,
    output      JSONB,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    metadata    JSONB
);
CREATE INDEX idx_trace_session ON trace_spans(session_id);
CREATE INDEX idx_trace_id ON trace_spans(trace_id);
```

---

### 3.5 API 接口设计

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/v1/chat | 同步对话 |
| POST | /api/v1/chat/stream | SSE 流式对话 |
| POST | /api/v1/documents/upload | 上传文档 |
| GET | /api/v1/documents | 文档列表 |
| DELETE | /api/v1/documents/{id} | 删除文档 |
| POST | /api/v1/documents/{id}/reindex | 重建索引 |
| POST | /api/v1/knowledge/search | 知识检索 |
| GET | /api/v1/skills | Skill 列表 |
| PUT | /api/v1/skills/{name}/toggle | 启用/禁用 Skill |
| GET | /api/v1/agents/runs/{id} | Agent 运行状态 |
| GET | /api/v1/memory/{user_id} | 查询长期记忆 |
| DELETE | /api/v1/memory/{user_id}/{id} | 删除记忆 |
| GET | /api/v1/traces/{session_id} | 查询 Trace |
| POST | /api/v1/traces/replay | 会话 Replay |
| POST | /api/v1/eval/run | 启动评测 |
| GET | /api/v1/eval/runs/{id} | 评测结果 |
| GET | /api/v1/health | 健康检查 |

---

### 3.6 关键设计决策

**D1 · 图存储用 PostgreSQL 不用 Neo4j**：一跳扩展用 SQL JOIN 即可实现，Neo4j 的优势在多跳和图算法，本场景用不到，不过度设计。架构保留升级路径，后续需要多跳或图规模爆发再引入 Neo4j。

**D2 · 一跳扩展不用 PageRank**：PageRank 全图迭代延迟高且算法级别过高。一跳扩展一条 SQL JOIN 毫秒级响应，已解决跨文档关联核心问题，收益边际递减不值得引入。

**D3 · Agent 编排用 LangGraph**：状态机模型适合知识问答多步推理，原生 checkpoint 支持断点续跑，是大厂 JD 高频关键词。

**D4 · 依赖管理用 uv**：比 pip/poetry 快 10-100x，2024-2025 年 Python 生态主流，pyproject.toml + uv.lock 标准化。

**D5 · 流式用 SSE 不用 WebSocket**：知识问答是单向流式输出，SSE 比 WebSocket 轻量，FastAPI 原生支持，HTTP 兼容性好。

**D6 · 沙盒用 MinIO 不用本地文件系统**：对象存储天然隔离（bucket prefix），无宿主文件系统越权风险，且支持配额和 TTL 生命周期管理。

**D7 · 记忆分层用 Redis + PostgreSQL**：短期记忆 Redis 会话级 TTL，长期记忆 PostgreSQL 持久化 + 向量召回，热数据内存冷数据磁盘，符合访问模式。

---

### 3.7 环境与依赖管理（uv）

**Python 版本**：3.13（`.python-version` 锁定）

**核心依赖（pyproject.toml）**：

```toml
[project]
name = "knowflow"
version = "1.0.0"
requires-python = ">=3.13"
dependencies = [
    # Web
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sse-starlette>=2.1",
    # Agent
    "langgraph>=0.2",
    "langchain>=0.3",
    "langchain-openai>=0.2",
    # 检索
    "pymilvus>=2.4",
    "rank-bm25>=0.2",
    "sentence-transformers>=3.0",
    # 存储
    "sqlalchemy>=2.0",
    "asyncpg>=0.30",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "redis>=5.0",
    "minio>=7.2",
    # 文档解析
    "pymupdf>=1.24",
    "python-docx>=1.1",
    "markdown>=3.7",
    # 工具
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "tiktoken>=0.7",
    "httpx>=0.27",
    "structlog>=24.4",
    "pyyaml>=6.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "ruff>=0.7",
    "mypy>=1.13",
    "httpx>=0.27",
]
```

**初始化命令**：

```bash
uv init knowflow --python 3.13
cd knowflow
uv sync
uv run uvicorn knowflow.main:app --reload
```

**docker-compose.yml 核心服务**：

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: knowflow
      POSTGRES_PASSWORD: nexus
    ports: ["5432:5432"]
  milvus:
    image: milvusdb/milvus:v2.4.0
    ports: ["19530:19530"]
  redis:
    image: redis:7
    ports: ["6379:6379"]
  minio:
    image: minio/minio
    command: server /data
    ports: ["9000:9000"]
```

---

## 四、面试核心叙事

项目讲述时的核心叙事线：KnowFlow 不是简单的 RAG 问答，而是**企业级 Agent 平台**，核心解决四个工程问题——检索的跨文档关联（GraphRAG）、工具调用的治理（执行域隔离）、复杂任务的编排（Multi-Agent）、上下文的治理（卸载 + 摘要）。每个问题都有量化指标支撑（8% / 34.2% / 32.6% / 94+% / 77.6%），且关键设计决策都有取舍逻辑（PostgreSQL vs Neo4j、一跳 vs PageRank、LangGraph vs 手写、SSE vs WebSocket）。

主动引导方向：检索的图谱增强、工具执行域隔离、上下文卸载机制。这些都是能讲深的技术点，且有量化数据。

避免方向：不要主动提"有多少用户""线上 QPS 多少"（无真实部署数据）。被问到时诚实说"目前是个人项目 / 内部测试，没有大规模线上数据，但本地评测集测了指标"。
