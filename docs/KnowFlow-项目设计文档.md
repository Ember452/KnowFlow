# KnowFlow 项目设计文档

> 可编排、可扩展的企业知识库 Agent 平台
> 版本：v2.0 ｜ 更新：2026-08-10 ｜ Python 3.13 + uv

---

## 一、简历写法

**KnowFlow —— 企业知识库 Agent 平台** ｜ 独立开发 ｜ 2026.04 - 2026.07

Python 3.13 / FastAPI / LangGraph / LangChain / MCP / Milvus / PostgreSQL / Redis / MinIO

面向企业内部异构文档的知识问答与任务自动化场景，独立设计并实现完整 Agent 平台，解决单路检索召回不全、工具注入膨胀、复杂任务编排、长会话上下文四大问题；覆盖"文档解析 → 混合检索 → 工具调用 → 多 Agent 编排 → 评测"全链路，内置 6 类工具、5 个 Skill、771 个单测，核心指标全部脚本实测可复现。

- 多 Agent 编排：实现复杂任务（竞品调研、报告撰写、多主题分析）自动拆解与子 Agent 并行执行，环节互不干扰；单环节失败自动降级不阻塞整体，进程中断后可从断点续跑；端到端耗时较串行下降均值 65.6%（8 任务并行最佳 84.1%）

- 安全高效的工具治理：针对工具 Schema 全量注入导致成本上升、FC 准确率下降的问题，设计按 Skill 激活状态动态裁剪模型可见工具集；实测可见工具数降 43.4%、Schema Token 降 45.2%、FC 准确率 100%（33 场景）；新工具声明式注册零侵入，依赖拓扑自动解析、循环依赖拒绝加载

- MCP 工具生态接入：基于 MCP 2.0 SDK 实现 stdio 协议工具网关，远程工具经适配器统一适配为本地工具接入统一注册表，自动纳入执行域隔离体系；内置 demo Server 独立子进程真实协议往返，覆盖"注册→治理→隔离→调用→降级"全链路，连接失败降级告警不阻塞对话

- 混合检索：针对纯向量检索关键词敏感度不足、召回不全的问题，设计向量 + BM25 双路召回经 RRF 融合、本地 reranker 精排，索引侧向量/BM25 双写、重建一致性可验证；50 条标注查询评测 Recall@10 33.6%、MRR 0.68，向量服务异常自动降级本地 BM25 不中断对话

- 记忆与上下文治理：搭建"短期 → 重要性筛选 → 压缩 → 长期"四级记忆管线，每 5 轮自动沉淀、语义去重防冗余、冲突检测留痕待审且不阻断写入；上下文按 token 预算分级，超长工具结果卸载进沙盒仅注入引用、可经工具读回，长会话不丢数据

---

## 二、产品需求文档（PRD）

### 2.1 项目背景

企业内部知识沉淀在大量异构文档中（产品手册、HR 政策、IT 工单、运营 SOP），传统关键词检索无法理解语义，员工查找信息效率低。大模型时代，基于 RAG 的知识问答 Agent 成为企业智能助手的主流形态，但现有方案存在四个核心问题：一是单路检索召回不全，纯向量对关键词不敏感、纯关键词无法理解语义；二是工具调用缺乏治理，模型可见工具过多导致 Token 浪费和调用准确率下降；三是多 Agent 协作缺乏编排，复杂任务无法拆解委派；四是上下文管理粗放，多轮工具调用容易撑爆上下文窗口。

KnowFlow 针对这四个问题，构建一个可编排、可扩展的企业知识库 Agent 平台，提供混合检索、工具治理、Multi-Agent 编排、上下文工程、沙盒文件系统、流式可观测六大核心能力。

### 2.2 项目定位

企业级知识库 Agent 平台，不是单一聊天机器人，而是可编排、可扩展的 Agent 基础设施。向上支撑企业智能助手、知识问答、自动化任务等应用场景，向下集成多模型、多工具、多知识源。核心价值在"编排"（Multi-Agent 协同 + 工具治理）和"扩展"（Skill 声明式加载 + MCP 工具接入）。

### 2.3 目标用户与场景

**目标用户**：企业员工（终端使用者，对话获取知识、执行任务）；平台开发者（二次开发，扩展 Skill、接入工具、定制 Agent）。

**核心场景**：知识问答（提问 → 混合检索 → 流式回答）、复杂任务（多步任务 → 主 Agent 拆解 → 委派子 Agent 并发执行 → 汇总）、工具调用（意图识别 → 激活 Skill → 动态注入工具 → 执行域隔离）、长期记忆（跨会话偏好 → 相关度召回 → 压缩注入）。

### 2.4 核心功能需求

| 编号 | 功能 | 描述 |
|---|---|---|
| F1 | 混合检索 | 文档上传→解析分块→Embedding 向量化→向量+BM25 双路召回→RRF 融合→reranker 精排 |
| F2 | 工具治理 | Skill 声明式加载 + 依赖开关 + 关联工具动态注入 + 四类执行域隔离 |
| F3 | Multi-Agent 编排 | 主/子 Agent 协同 + task 委派 + checkpoint 父子关系 + 并发执行 + 可观测 |
| F4 | 上下文工程 | 滑动窗口 + 动态摘要 + 超阈值卸载沙盒 + checkpoint 异步 run |
| F5 | 沙盒文件系统 | 会话隔离 workspace + 虚拟路径 + 受控文件工具 + MinIO 后端 |
| F6 | 流式与可观测 | SSE 流式 + 工具进度回显 + 全链路 Trace + 会话 replay + 离线评测 + 长期记忆 |

### 2.5 关键性能指标

| 指标 | 目标值 | 测量方式 |
|---|---|---|
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
| 关系库 | PostgreSQL | 业务数据 |
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
│混合  │   │工具治理│  │上下文  │ │沙盒    │ │流式+可观测 │
│检索  │   │模块   │  │工程    │ │文件系统│ │+记忆       │
│模块  │   │       │  │模块    │ │模块    │ │模块        │
└──┬──┘   └───┬───┘  └───┬────┘ └───┬────┘ └───┬────────┘
   │          │          │          │          │
┌──▼──────────▼──────────▼──────────▼──────────▼───────────────┐
│                        存储层                                 │
│  Milvus(向量) · PostgreSQL(业务) · MinIO(文件)           │
│  Redis(会话+记忆+checkpoint)                                  │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 完整项目结构

> 项目目录结构已抽取为独立文档：[KnowFlow-项目结构.md](./KnowFlow-项目结构.md)，按大厂工程规范重构（src 布局 + 分层架构 + API 版本化 + Repository 模式 + 独立 Worker + CI/CD），结构变更以该文档为准。

**文件规模统计**（以 [KnowFlow-项目结构.md](./KnowFlow-项目结构.md) 为准）：核心源码约 110 个文件，Worker 独立进程 3 个，测试约 23 个，配置/CI/CD/部署/文档约 35 个，总计约 170 个文件。

---

### 3.4 模块详细设计

#### 模块一：混合检索（retrieval/）

**核心链路**：文档上传 → 解析分块 → Embedding 向量化 → 索引时向量/BM25 双写 → 查询时 Hybrid 召回 → reranker 精排

**核心类设计**：

`RetrievalPipeline`（索引编排 pipeline）：
- `index_document(doc_id)` → 调用 parser → splitter → embedding → 写入 vector_store + bm25_store
- `reindex_document(doc_id)` → 先清理向量/BM25/chunks 再重新索引

`HybridSearch`（向量 + BM25 融合）：
- `vector_search(query, top_k)` → Milvus 向量召回
- `bm25_search(query, top_k)` → PostgreSQL tsvector 全文检索
- `fuse(vector_results, bm25_results)` → RRF（Reciprocal Rank Fusion）融合

`HybridRetriever`（统一检索入口）：
- `retrieve(query, top_k)` → hybrid_search 召回 → reranker 精排 → 结果缓存（Redis md5 key）
- 结果带文档出处（doc_id/doc_title）供引用溯源

`Reranker`（精排）：
- `rerank(query, chunks)` → 本地交叉编码器对 (query, chunk) 打分 → 按分数重排

`EmbeddingService` / `BM25Store`：
- Ollama embedding 批量向量化，Chroma 持久化向量库；BM25 应用内存索引（启动时从 chunks 表全量加载）
- 向量库不可用且未强制要求时自动降级本地 BM25，不中断对话

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

**核心机制**：主 Agent 规划（注入子 Agent 可用工具清单）→ task 委派 → 子 Agent 子线程隔离（SUBAGENT 角色工具循环）→ 并发执行 → checkpoint 父子关系 → 结果汇总

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
- `plan(query)` → 任务规划（是否需要委派、委派给几个子 Agent）；prompt 注入子 Agent 可用工具清单，避免拆出工具不可达的任务
- `delegate(subtasks)` → 创建 TaskDelegation，委派给子 Agent
- `summarize(results)` → 汇总子 Agent 结果

`Subagent`：
- `execute(task)` → 子线程隔离上下文执行任务
- 独立 ContextManager 实例，与主 Agent 上下文隔离
- 注入 ToolOrchestrator 后以 SUBAGENT 角色跑工具循环：subagent_only 域工具（如 code_review / report_writing）仅子 Agent 可见，工具调用经 on_tool 回调上抛（标注 subtask_id）可观测，调用记录随子任务结果返回

`Orchestrator`：
- `run_concurrent(subtasks)` → asyncio.gather 并发执行多个子 Agent
- 超时控制、降级策略（单个子 Agent 失败不阻塞整体）
- 结果聚合
- 子任务按需检索：各子任务用自己的文本检索知识库，不共享主 Agent 预检索上下文（跨主题不串扰）；检索失败/无结果回退共享上下文

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
- `EvalRunner` 跑评测集（knowledge_qa_eval.jsonl / retrieval_eval.jsonl）
- 指标：Recall@K / MRR / NDCG / 要点命中率 / 工具调用准确率
- 生成评测报告（指标汇总表 + 场景明细）

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

**D1 · Agent 编排用 LangGraph**：状态机模型适合知识问答多步推理，原生 checkpoint 支持断点续跑，是大厂 JD 高频关键词。

**D2 · 依赖管理用 uv**：比 pip/poetry 快 10-100x，2024-2025 年 Python 生态主流，pyproject.toml + uv.lock 标准化。

**D3 · 流式用 SSE 不用 WebSocket**：知识问答是单向流式输出，SSE 比 WebSocket 轻量，FastAPI 原生支持，HTTP 兼容性好。

**D4 · 沙盒用 MinIO 不用本地文件系统**：对象存储天然隔离（bucket prefix），无宿主文件系统越权风险，且支持配额和 TTL 生命周期管理。

**D5 · 记忆分层用 Redis + PostgreSQL**：短期记忆 Redis 会话级 TTL，长期记忆 PostgreSQL 持久化 + 向量召回，热数据内存冷数据磁盘，符合访问模式。

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

项目讲述时的核心叙事线：KnowFlow 不是简单的 RAG 问答，而是**企业级 Agent 平台**，核心解决四个工程问题——检索的召回（混合检索）、工具调用的治理（执行域隔离）、复杂任务的编排（Multi-Agent）、上下文的治理（卸载 + 摘要）。每个问题都有量化指标支撑（33.6% / 34.2% / 32.6% / 94+% / 77.6%），且关键设计决策都有取舍逻辑（RRF vs 加权融合、LangGraph vs 手写、SSE vs WebSocket）。

主动引导方向：混合检索与降级、工具执行域隔离、上下文卸载机制。这些都是能讲深的技术点，且有量化数据。

避免方向：不要主动提"有多少用户""线上 QPS 多少"（无真实部署数据）。被问到时诚实说"目前是个人项目 / 内部测试，没有大规模线上数据，但本地评测集测了指标"。

---

## 五、研究报告生成平台（V2 全面改造方向）

> 本章为 V2 改造方向：在既有"混合检索 + 工具治理 + Multi-Agent 编排 + 上下文工程"全链路之上，
> 扩展"多 Agent 研究报告生成 + 飞书 MCP 发布"闭环。决策依据见 `docs/adr/0008`、`docs/adr/0009`；
> 实施节奏与验收标准见《开发计划》P12/P13。

### 5.1 改造目标与定位

V2 将 KnowFlow 从"问答式知识库 Agent 平台"升级为"**研究报告生成平台**"：

- 用户提出需求 → 平台按需求拆解为多 Agent 并行调研（知识库检索 / 记忆检索 / 联网搜索）→
  生成**深度研究报告 / 知识库总结报告**（结构化章节 + 引用溯源）→ 一键写入**飞书云文档**。
- 三个差异化卖点：
  1. **多源证据融合**：知识库（混合检索）、记忆（长期记忆召回）、联网（duckduckgo）三类信息源按需组合；
  2. **引用可溯源防幻觉**：报告每个结论强制 `[n]` 标注，Reviewer 校验引用真实性，量化评测引用覆盖率/幻觉率；
  3. **真实 MCP 生态接入**：自建飞书 MCP server，走通"注册 → 治理 → 隔离 → 调用 → trace"全链路。

### 5.2 整体架构（报告流水线）

报告生成是天然流水线，编排模式定为六阶段，**独立于问答链路**（决策见 ADR 0008）：

```
用户需求
  │
  ▼
Planner ── 规划: 报告大纲(章节) + 每章检索计划 + 引用规范
  │
  ▼
Researcher × N ── 迭代调研(可选): 初始查询 → LLM 缺口评估 → 追加查询再检索
  ├─ 知识库 Agent    混合检索(direct 域, 带 doc_id 出处)
  ├─ 记忆 Agent      长期记忆召回(直接域, memory_tool)
  └─ 联网 Agent      duckduckgo(subagent_only 域, search_tool)
  │
  ▼
Synthesizer ── 证据融合: 去重/组织 → 证据包(带出处的片段集合)
  │
  ▼
Writer × N ── 分章节并行撰写(章节独立 context budget, 强制 [n] 标注)
  │
  ▼
Reviewer ── 递进式三阶段核查: 引用真实性 → 结论支持度 → 主动事实核查(可选)
            不通过打回重写
  │
  ▼
Publisher ── 输出: Markdown 落盘沙盒 / 飞书 MCP 写入云文档
```

### 5.3 Agent 角色设计

| 角色 | 职责 | 信息源 / 工具 | 复用基础 |
|---|---|---|---|
| Planner | 拆解报告大纲、分配检索计划 | 无 | MainAgent 规划能力 |
| Researcher（知识库） | 按任务意图检索知识库 | 混合检索（direct 域） | Subagent + 注入独立 retriever |
| Researcher（记忆） | 召回跨会话长期记忆 | memory_tool（直接域） | memory/recall.py 包装 |
| Researcher（联网） | 联网搜集公开信息 | search_tool（subagent_only 域） | 既有 SearchTool |
| Synthesizer | 证据去重、按章节组织证据包 | 无 | — |
| Writer | 分章节撰写，强制 `[n]` 引用标注 | 沙盒（章节草稿落盘） | Subagent + context budget |
| Reviewer | 递进式三阶段核查：引用真实性（规则）→ 结论支持度（LLM）→ 主动事实核查（可选，陈述提取 + 交叉检索验证），打回重写 | 沙盒读取 + 知识库/联网检索 | 质量门禁（复用 subagent.quality_check） |
| Publisher | 报告输出与飞书发布 | feishu MCP（skill_only 域） | MCP 注册链路 |

### 5.4 报告产物与引用溯源

**产物结构**（`ReportResult`）：

- `spec`：报告大纲（标题 / 章节列表 / 检索计划）
- `evidence`：证据包（每个片段带 source_type / doc_id / url / 原文）
- `chapters`：章节正文（`[n]` 引用标注，n 指向证据包下标）
- `references`：参考文献表（doc_title / url / 来源）
- `review`：Reviewer 结论（通过 / 问题清单）

**引用溯源规范**：

1. Writer 只允许引用证据包中真实存在的片段，`[n]` 与证据包下标一一对应；
2. Reviewer 递进式三阶段核查：① 引用是否真实命中证据包（规则，防幻觉）；② 结论是否被所引证据支持（LLM，防误导）；③ 主动事实核查（可选，注入检索源时启用）：提取关键陈述 → 用陈述交叉检索知识库/联网 → 判定支持/矛盾/证据不足，仅"矛盾"打回、"证据不足"降级告警，每章核查预算 3 条；
3. 校验不通过 → 携带问题清单打回对应章节重写（复用质量门禁重试机制）。

**评测指标**（入 `eval/`，与既有指标体系一致）：引用覆盖率（报告 `[n]` 均可定位证据）、幻觉率（无法定位/不支持结论的引用占比）、章节完整率。

### 5.5 飞书 MCP 接入设计

- **接入形态**：官方 server 优先 + 自建兜底。优先接入飞书开放平台官方 lark-openapi-mcp（stdio 协议，npx 启动），经 `register_mcp_server` 的 `allow_tools` 白名单过滤后只注册云文档相关工具；无 Node 环境时回退到自建 `tools/mcp/servers/feishu/` MCP server（lark SDK 封装，工具名固定 `create_doc` / `append_to_doc` / `update_doc`）；
- **接入链路**：`settings.mcp_servers` 配置声明（含 `allow_tools` 白名单）→ `register_mcp_server` 注册 → `McpToolAdapter` 适配为 BaseTool → 工具注册表 → 域隔离（skill_only，仅发布阶段激活注入）→ 运行时权限校验 → 全链路 trace。**不改动任何既有工具治理代码**；
- **容错设计**：① MCP 调用超时（`mcp_call_timeout_seconds`，默认 30s，超时降级为失败 ToolResult）；② server 连接失败/单工具注册失败降级不阻塞启动；③ 发布幂等 + 指数退避重试（1s/3s/9s 共 3 次）；④ 凭证缺失/token 过期返回可读提示（"请重新授权飞书"）不抛堆栈；⑤ 分章节写入单章失败标记缺失章节，不整体回滚；⑥ 发布失败降级为沙盒 Markdown 交付，不影响报告生成；
- **发布流程**：报告生成完成 → Publisher 激活飞书工具 → 创建云文档（标题 + 分章节写入 + 引用标注）→ 返回文档链接；
- **凭证要求**：飞书开放平台自建应用（app_id / app_secret + 云文档读写权限 + 用户授权 token），仅环境变量配置，不落库。

### 5.6 新增 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/v1/reports | 创建报告任务（触发 Planner → 并行调研 → 撰写 → 审查） |
| GET | /api/v1/reports/{id} | 报告任务状态与阶段进度（SSE progress 事件） |
| GET | /api/v1/reports/{id}/result | 报告产物（spec / evidence / chapters / references） |
| POST | /api/v1/reports/{id}/publish | 发布到飞书云文档（返回文档链接） |

### 5.7 关键设计决策（V2 新增）

**D8 · 报告链路用独立流水线模块，不扩展现有 orchestrator**：报告产出物（结构化章节 + 证据包）与问答产出物（单答案）完全不同，且多出调研/融合/审查/发布阶段，混入现有状态机会互相污染。独立 `agents/report/` 复用 Subagent / concurrent / checkpoint 基础设施，问答链路零改动（ADR 0008）。

**D9 · 飞书接入走 MCP server，不直接调 SDK**：直接调 lark SDK 最快，但绕开既有工具治理体系，无法证明"MCP 生态可扩展"这一项目核心能力。自建 MCP server 走既有注册链路，零侵入且补齐真实 MCP 接入案例（ADR 0009）。

**D12 · 调研升级为可选迭代式（DeepSearch 范式），审查升级为递进三阶段**：对齐业界主流 Deep Research 编排——调研侧：初始查询 → 三源检索 → LLM 缺口评估（信息是否足以撰写章节）→ 不足则生成追加查询再检索，最多 2 轮、每轮最多 3 条追加查询、已执行查询去重、评估失败降级为单轮，`iterative_research` 开关默认关闭不破坏既有行为；审查侧：在"引用规则 + 结论支持度"之后增加主动事实核查（提取关键陈述 → 陈述作为查询交叉检索 → 判定支持/矛盾/证据不足），仅矛盾打回、证据不足降级告警，`fact_check` 开关默认关闭。两项均为可选能力，Token 成本有预算控制，生产按需开启。

**D10 · 引用溯源为报告硬性规范**：报告场景幻觉危害高于问答，强制 `[n]` 标注 + Reviewer 双校验 + 量化评测，对齐"严禁伪造数据"红线。

**D11 · 搜索源可配置**：默认 duckduckgo（零成本），SearchTool 的查询实现封装为可替换（换源只改配置与实现类），避免单一源可用性风险。

### 5.8 阶段规划

| 阶段 | 内容 | 验收要点 |
|---|---|---|
| M0 | 报告流水线 MVP（规划→知识库+联网调研→融合→撰写→审查，Markdown 输出） | 六阶段跑通，报告可落盘沙盒 |
| M1 | 记忆 Agent + 引用溯源评测 | memory_tool 接入；引用覆盖率/幻觉率入 eval |
| M2 | 飞书 MCP + 发布流程 | 报告一键写入飞书云文档，trace 闭环 |
| M3 | 打磨：分章节并行撰写、长报告断点续跑、报告模板 | 指标实测 + 面试叙事更新 |
