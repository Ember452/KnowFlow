# KnowFlow 简历写法

> 面向 Agent 开发实习/岗位面试的项目经历写法，共三个版本：
> **完整版（5 条）** 常规简历推荐 / **精简版（4 条）** 版面紧张时用 / **最全版（不限条数）** 简历空间充裕或需要深度展示时用。
>
> **数据口径声明（红线）**：本文所有量化指标均为仓库内实测值，可溯源复现（见"四、指标溯源"）。严禁替换为设计目标值（如 77.6%、+8%），面试被追问时须如实说明测试口径。

---

## 一、完整版（5 条 · 常规简历推荐）

> **KnowFlow — 企业知识库 Agent 平台**（个人项目）
> Python 3.13 / FastAPI / LangGraph / LangChain / Milvus / PostgreSQL / Redis / MinIO / Docker

- **GraphRAG 混合检索**：针对纯向量检索跨文档关联查询召回差的问题，自研 LLM 实体-关系抽取构建知识图谱（PostgreSQL 存储，一跳扩展仅需 SQL JOIN），向量（Milvus）+ BM25 双路召回经 RRF 融合后做实体一跳跨文档扩展与精排；50 条标注查询评测中跨文档查询 MRR 0.80→0.87

- **工具治理与执行域隔离**：针对工具 Schema 全量注入导致成本高、FC 准确率下降的问题，设计 YAML frontmatter 声明式 Skill 体系 + 四类执行域（direct / skill_only / subagent_only / internal）动态计算可见工具集，按意图激活注入；实测可见工具数降 43.4%、注入 Schema Token 降 45.2%、Function Calling 准确率 100%（33 场景）；Skill 零侵入注册、依赖拓扑自动解析、循环依赖拒绝加载

- **Multi-Agent 编排**：基于 LangGraph 状态机（理解→规划→委派→执行→汇总）实现主 Agent 任务拆解与子 Agent 独立上下文并发执行（asyncio.gather + 60s 超时 + 单子失败降级不阻塞整体），checkpoint（PostgresSaver）记录父子 lineage 支持断点续跑；实测并发较串行端到端耗时下降均值 65.6%（8 子任务最佳 84.1%）

- **分层记忆与跨会话个性化**：设计"短期（Redis TTL）→ 重要性筛选（LLM 0-10 打分 + 关键词规则兜底，离线可测）→ LLM 压缩 → 长期存储（PostgreSQL + 向量召回）"四层记忆管线，每 5 轮对话自动沉淀、按用户隔离；沉淀时语义去重（embedding 余弦相似度 ≥0.9 判重，无向量时文本相似度兜底），重复偏好覆盖更新并保留更高重要性，避免冗余沉淀

- **上下文预算管理**：按 32000 token 预算为历史/工具/检索/记忆分配配额，防止长会话挤占检索空间；超限按"窗口裁剪 → LLM 摘要 → 沙盒卸载 → 截断"四级处理，超长工具结果（4000 token）写沙盒文件仅注入引用，LLM 需要时经工具读回，不丢数据

---

## 二、精简版（4 条 · 版面紧张时用）

> **KnowFlow — 企业知识库 Agent 平台**（个人项目）
> Python 3.13 / FastAPI / LangGraph / Milvus / PostgreSQL / MinIO / Docker

- 自研 GraphRAG 检索：LLM 实体抽取构建图谱（PG 存储），向量+BM25 RRF 融合后实体一跳跨文档扩展与精排，跨文档查询 MRR 0.80→0.87
- 工具治理：声明式 Skill + 四类执行域隔离动态裁剪工具集，可见工具数降 43.4%、Schema Token 降 45.2%、FC 准确率 100%
- Multi-Agent：LangGraph 状态机编排主/子 Agent，子线程上下文隔离并发执行 + checkpoint 断点续跑，端到端耗时下降 65.6%
- 分层记忆：短期（Redis）→ 重要性打分 + LLM 压缩 → 长期（PG + 向量召回），每 5 轮自动沉淀、语义去重合并重复偏好，用户偏好跨会话复用

---

## 三、最全版（不限条数 · 深度展示用）

> 以下每条均为独立简历条目，按面试岗位侧重点自由取舍；每一条都包含"痛点 → 方案 → 量化验证"完整叙事，可直接复制。

### 1. GraphRAG 混合检索

自研 LLM 实体-关系抽取构建企业知识图谱（PostgreSQL 存储而非 Neo4j：一跳扩展仅需 SQL JOIN，规避多跳场景之外的过度设计），向量（Milvus）与 BM25 双路召回经 RRF 融合（k=60）后，基于命中实体做一跳跨文档扩展、再统一精排，解决"张三负责什么"这类跨文档关联查询召回差的问题；embedding/reranker 支持 API（qwen3.7-text-embedding 1024 维 / qwen3-rerank）与本地（sentence-transformers / cross-encoder）双模式；50 条标注查询（直接/跨文档/语义三类）评测中跨文档查询 MRR 0.80→0.87、整体 MRR +0.02

### 2. 工具治理与执行域隔离

针对工具越多、注入 LLM 的 Schema 越大导致成本上升与 FC 准确率下降的问题，设计 YAML frontmatter 声明式 Skill 体系（零侵入：新建目录 + SKILL.md 即注册）+ 四类执行域（direct 恒可见 / skill_only 按激活 / subagent_only 按角色 / internal 永不可见），意图识别激活 Skill 后由 VisibilityCalculator 动态计算可见工具集；实测可见工具数 6→3.39（降 43.4%）、Schema Token 504→276（降 45.2%）、Function Calling 准确率 100%（33 场景）；Skill 依赖拓扑自动解析、循环依赖检测到即拒绝加载

### 3. Multi-Agent 编排

基于 LangGraph 状态机（理解→规划→委派→执行→汇总）实现主 Agent 任务拆解、子 Agent 独立上下文并发执行（asyncio.gather + 60s 超时 + 单子失败降级不阻塞整体、汇总时如实标注缺失部分）；checkpoint 采用 PostgresSaver 记录父子 lineage（thread_id = run_id），支持 kill 进程后按 checkpoint_id 断点续跑；checkpoint_id 使用 LangGraph 同款 uuid6 保证字符串序=时间序，规避 uuid1 时间戳回绕导致的"取最新错乱"；实测并发较串行端到端耗时下降均值 65.6%（2/3/5/8 子任务：42.5% / 62.2% / 73.5% / 84.1%，调度开销可忽略）

### 4. 分层记忆与跨会话个性化

针对 Agent 无状态、跨会话丢失用户偏好的问题，实现四级记忆管线：短期（Redis TTL）→ 重要性筛选（LLM 0-10 打分 + 关键词规则兜底保证离线可测）→ LLM 压缩 → 长期存储（PostgreSQL + 向量召回，按用户隔离）；每 5 轮对话自动沉淀、召回结果注入系统提示；沉淀时语义去重（embedding 余弦相似度 ≥0.9 判重，无向量时 SequenceMatcher 文本相似度兜底），重复偏好覆盖更新（内容取新表述、importance 取最大值），避免冗余沉淀；召回命中标记 last_recall 参与时间衰减

### 5. 上下文预算管理

按 32000 token 总预算以固定比例分配 system 10% / 历史 35% / 工具 20% / 检索 25% / 记忆 10%，防止长会话挤占检索与记忆空间；超限按四级处理：滑动窗口裁剪（20 轮）→ LLM 摘要替代历史 → 长文本沙盒卸载 → 截断兜底；超长工具/检索结果（≥4000 token）写入会话沙盒 `/workspace/spilled/`，上下文仅注入 `{"spilled": true, "path": ...}` 引用，LLM 需要时经 file_read_tool 读回——"长上下文不截断，而是挪到可读回的地方"；每次处理动作记录进 ContextStats 供 Trace 观测

### 6. 工具执行沙盒与安全隔离

针对 Agent 工具调用越权风险，实现 MinIO 沙盒工作区 + 会话级虚拟路径映射（session 隔离），AccessControl 严格校验路径合法性：拦截路径穿越（`../`）、非 workspace 前缀、前缀伪造（`/workspacex`）；配额管理限制单次工具调用资源消耗；工具仅可读写本会话 workspace，越权即抛 PermissionDenied 异常，全程行为可测

### 7. 全链路可观测

Tracer 基于 contextvars 传播 trace_id，嵌套 span 覆盖检索/工具调用/记忆召回/编排全链路（父子 span 继承 session_id），SpanCollector 内存缓冲 + 批量异步落库 + 后台自动刷新，失败降级不阻塞主流程；Replayer 按 checkpoint 恢复状态 + 时间序事件重放（不执行任何 LLM 调用），支持断点续跑演示与事故复盘可视化

### 8. 异步索引与任务流水线

文档上传后由独立 Worker 异步执行"解析 → 递归分块 → embedding → LLM 实体抽取 → 图谱/向量/BM25 三写入库"完整索引管线，与 API 主流程解耦，索引任务状态可查询

### 9. 统一评测体系

构建三类指标的离线评测体系：检索（Recall@K / MRR / NDCG）、QA 要点命中率、Function Calling 准确率；50 条检索 + 60 条 QA 标注评测集（合成企业语料），`uv run python eval/scripts/run_eval.py --all` 单命令复现全部指标；静态模式（无模型依赖、结果可复现）与真实模式（真实 LLM/检索链路）双口径，产出 Markdown 报告入库

### 10. 工程化交付

GitHub Actions CI 门禁（ruff / ruff-format / mypy / pytest --cov / pre-commit 全绿）+ CD 流水线（main 合并构建镜像推 ghcr）；multi-stage Dockerfile（builder 装依赖 → runtime 精简 + 非 root + healthcheck）；K8s 七清单（namespace / configmap / secrets / api-deployment / api-service / worker-deployment / HPA 水平扩缩容 2-6 副本）；7 条 ADR 记录架构决策（图谱存储、一跳扩展、checkpoint、SSE、MinIO 沙盒等）；核心模块测试覆盖率 89%（实测，`uv run pytest tests/unit -q --cov=src` 复现）

---

## 四、指标溯源

| 指标 | 实测值 | 溯源文件 | 复现命令 |
|---|---|---|---|
| 跨文档查询 MRR 0.80→0.87 | +0.0213 整体 MRR | `eval/reports/compare_20260608.md` | `uv run python eval/scripts/compare_baseline.py` |
| GraphRAG Recall@10 提升 | -1.0%（未达 +8% 目标，如实呈现） | `eval/reports/compare_20260608.md` | 同上 |
| 可见工具数下降 | -43.4% | `docs/benchmarks/tool_governance_20260807.md` | `uv run python scripts/benchmark_tools.py` |
| Schema Token 下降 | -45.2% | `docs/benchmarks/tool_governance_20260807.md` | 同上 |
| FC 准确率 | 100%（33 场景，静态代理指标） | `docs/benchmarks/tool_governance_20260807.md` | 同上 |
| 并发较串行耗时下降 | 65.6%（均值，最佳 84.1%） | `docs/benchmarks/multiagent_20260807.md` | `uv run python scripts/benchmark_multiagent.py` |
| 测试覆盖率 | 89%（src 整体） | commit-log M2 核心模块 ≥70% | `uv run pytest tests/unit -q --cov=src` |
| 汇总 | 五指标总览 | `eval/reports/final_report.md` | - |

> **诚实边界**（面试必须主动说明）：指标均为本地评测（合成语料 5 篇 43 chunk + 静态/真实双模式），无线上数据；FC 100% 是"预期工具在可见集中"的静态代理指标，真实 LLM 调用准确率需真实模式实测；检索 Recall@10 提升 -1.0% 未达 +8% 目标，跨文档场景 MRR 已现正向趋势。真实模式测试步骤见 `docs/tests/指标测试-*.md` 六份文档。

---

## 五、高频追问应答速查

| 追问 | 应答要点 |
|---|---|
| 为什么 PG 存图不用 Neo4j？ | 一跳扩展一条 SQL JOIN 毫秒级完成；Neo4j 优势在多跳与图算法，当前场景边际收益递减；查询封装在 graph_store 单一出口，需要多跳再迁移（ADR 0001/0002） |
| RRF 融合参数 k=60 怎么定的？ | 融合权重随 k 趋缓，60 为业界常用默认；关键收益是双路互补而非调参 |
| 执行域隔离判定逻辑？ | 意图识别激活 Skill → VisibilityCalculator：direct 恒可见 / skill_only 按激活 / subagent_only 按角色 / internal 永不可见 |
| 子 Agent 上下文隔离怎么做？ | 子 Agent 只看任务描述 + 共享预检索上下文，不注入主 Agent 完整历史；各自挂独立 ContextManager（窗口/预算互不影响） |
| 断点续跑演示过吗？ | kill 进程后以同一 thread_id + checkpoint_id 调 graph.ainvoke 恢复（docs/demo_checkpoint.md）；委派里程碑 checkpoint_id 可精确定位 |
| 记忆去重 0.9 阈值为什么？ | 语义余弦相似度 0.9 表示表述高度一致；可配置（memory_dedup_threshold）；embedding 不可用时 SequenceMatcher 兜底，保证离线可测 |
| 为什么覆盖更新而不是丢弃？ | 内容取新表述保留最新信息，importance 取 max 不丢失重要性信号 |
| 为什么卸载到沙盒而不直接丢？ | 工具结果可能被后续追问引用（"把刚才的数据存成 CSV"），写文件后可读回，只丢"上下文占用"不丢"数据" |
| checkpoint_id 为什么用 uuid6？ | uuid1 时间戳低位在前会周期性回绕，saver 按字符串排序取最新会选错；uuid6 时间高位在前，字符串序=时间序 |
| 指标怎么测的？ | 静态模式（合成语料 + 规则/代理指标）可复现；真实模式按 docs/tests/ 六份文档实测，如实说明口径与边界 |
