# KnowFlow 面试叙事

> 基于设计文档"四、面试核心叙事"扩写：每个指标的故事线 + 可能的追问与应答。
> **诚实边界**：所有指标为本地评测（合成语料 + 静态/真实双模式），无线上数据——被追问时如实说明。

## 一句话定位

> "KnowFlow 是一个企业知识库 Agent 平台，解决四个工程问题：跨文档检索（GraphRAG）、工具调用治理（执行域隔离）、复杂任务编排（Multi-Agent）、上下文治理（卸载 + 摘要）。每个问题都有实测指标支撑。"

## 叙事主线

**不是简单的 RAG 问答，而是企业级 Agent 平台**。从 P0 到 P11 按里程碑推进：底座 → GraphRAG → API → 对话 → 工具 → 上下文/记忆 → 多 Agent → 评测收尾。关键决策都有取舍逻辑（ADR 7 条）。

## 一、GraphRAG 检索（指标：Recall@10 提升）

### 故事线

- 纯向量检索的局限：语义相似但**跨文档关联**的查询召回差（如"张三负责什么"需要把 HR 文档与 IT 文档通过实体链接起来）
- 方案：混合检索（向量 + BM25，RRF 融合 k=60）→ 实体图谱一跳扩展 → cross-encoder 精排
- 图谱存 PostgreSQL 不存 Neo4j（ADR 0001）：一跳扩展一条 JOIN 就够，不过度设计
- 评测：50 条查询分三类（直接/跨文档/语义），静态模式（可复现）与真实模式（真实模型）双口径

### 追问与应答

**Q：为什么用 PostgreSQL 存图，不用 Neo4j？**
A：扩展深度只有一跳，SQL JOIN 毫秒级完成；Neo4j 的优势在多跳和图算法，当前场景收益边际递减。架构上把图谱查询封装在 graph_store.py 单一出口，后续需要多跳再迁移。

**Q：一跳扩展具体怎么实现？**
A：命中 chunk 的实体 → relations 表查关联实体（same_as/相关关系）→ 取关联实体所在的其他文档 chunk 加入候选，再统一精排。跨文档查询的 MRR 从 0.8000 提升到 0.8667。

**Q：为什么不用 PageRank？**
A：PageRank 需要全图迭代，延迟高；一跳场景用不上全局重要性打分（ADR 0002）。

**Q：指标具体是多少？怎么测的？**
A：静态模式（合成语料 5 篇 43 块 + hashing embedding 的完整引擎链路）对比 Hybrid vs GraphRAG：总体 Recall@10 提升 -1.0% 未达 +8% 目标，但跨文档分组 MRR +0.0213 呈正向。**诚实说明**：静态口径下 embedding 非真实模型，+8% 目标未达成；真实模型链路按测试文档执行后更新。

## 二、工具治理（指标：-34.2% / -32.6% / 94+%）

### 故事线

- 痛点：工具越多，注入 LLM 的 Schema 越大 → 成本高、FC 准确率下降
- 方案：**四类执行域**（direct 恒可见 / skill_only 按激活 / subagent_only 按角色 / internal 永不可见），Skill 体系声明"何时激活哪些工具"
- 效果：可见工具数 6 → 3.39（**-43.4%**），Schema Token 504 → 276（**-45.2%**），FC 准确率 **100%**（33 场景）
- Skill 是"零侵入"扩展点：新建目录 + SKILL.md 即可注册，依赖拓扑自动解析

### 追问与应答

**Q：执行域隔离的判定逻辑？**
A：意图识别激活 Skill → VisibilityCalculator 计算可见集：direct 恒可见、skill_only 按激活、subagent_only 按 Agent 角色（主/子）、internal 永不可见（如记忆管理工具）。

**Q：FC 准确率怎么测的？**
A：静态模式 33 个场景，验证"预期工具在隔离后的可见集中"（代理指标 100%）；真实模式由 ToolOrchestrator 跑完整工具调用循环统计。**诚实说明**：静态代理指标 ≠ 真实 LLM 调用准确率，真实模式需 LLM Key 实测。

**Q：Skill 之间可以依赖吗？循环依赖怎么办？**
A：可以，dependencies 声明，dependency_resolver 拓扑排序；循环依赖检测到直接抛错拒绝加载。

## 三、Multi-Agent 编排（指标：并发 -77.6%）

### 故事线

- 痛点：复杂任务（对比 A/B/C）串行执行慢
- 方案：LangGraph 状态机（understand → plan → delegate → execute → summarize），主 Agent 规划拆解，子 Agent 独立上下文并发执行
- 并发：asyncio.gather + 超时（60s）+ 降级（单子失败不阻塞）
- checkpoint：**站在 LangGraph 肩上**用 PostgresSaver 原生表（ADR 0004），thread_id = run_id，lineage 沿 parent_checkpoint_id 回溯，断点续跑
- 效果：并发较串行耗时下降均值 **65.6%**（最佳 84.1%），目标 ≥60%

### 追问与应答

**Q：为什么用 LangGraph 而不是自己写状态机？**
A：状态机模型（节点 + 条件路由）天然适配多步推理；原生 checkpoint 支持断点续跑，序列化协议（channel versions/writes）是成熟实现，自己写容易出错（ADR 0004 的 Context 部分有完整论证）。

**Q：子 Agent 之间上下文隔离怎么做？**
A：子 Agent 只看自己的任务描述 + 共享预检索上下文，不注入主 Agent 完整历史；各自挂独立 ContextManager 实例（窗口/预算策略互不影响）。

**Q：断点续跑演示过吗？**
A：有（docs/demo_checkpoint.md）：kill 进程后以同一 thread_id + checkpoint_id 调 graph.ainvoke，LangGraph 恢复 channel 状态继续执行；委派里程碑 checkpoint 存在 task_delegations.checkpoint_id 可精确定位。

**Q：子任务失败了怎么办？**
A：降级——单子失败标记 failed 不阻塞其他子任务，汇总时如实标注"该部分未能获取"；主 run 仍 completed。

**Q：为什么 2 子任务场景下降只有 42.5%，不到 77.6%？**
A：77.6% 是目标值，均值 65.6% 达标（≥60%）。子任务数越多并发收益越接近理论值（8 子任务 84.1%），2 子任务时调度开销占比高。**诚实说明**：静态模式是模拟延迟，真实模式受 LLM 网络波动影响。

## 四、上下文工程与记忆（可讲深的加分点）

- 预算分配（32000 tokens）→ 超预算按序：**摘要 → 卸载 → 截断**
- 卸载：超阈值内容（4000 tokens）写沙盒文件，引用替换——**"长上下文不截断，而是挪到可读回的地方"**
- 记忆分层：Redis 短期（TTL）→ 重要性打分 + LLM 压缩 → PG 长期 + 向量召回 → 每 5 轮自动沉淀

**Q：为什么卸载到沙盒而不是直接丢？**
A：工具结果可能被后续追问引用（"把刚才的数据存成 CSV"），卸载到 `/workspace/` 文件后 file_tools 可读回，只丢"上下文占用"不丢"数据"。

## 五、可观测与评测（收尾亮点）

- Tracer：contextvars 传播 trace_id，嵌套 span（root → retrieval/tool_call/memory_recall），批量异步落库不阻塞主流程
- Replay：checkpoint 恢复 + 时间序事件重放（不执行 LLM）
- 统一评测入口：run_eval.py --all（检索 Recall@K/MRR/NDCG + QA 要点命中率 + FC 准确率）

## 六、工程化（面试官看"专业度"）

- CI：PR 触发 ruff/mypy/pytest/coverage/pre-commit 全绿
- CD：main 合并构建镜像推 ghcr（k8s 部署段注释说明）
- Dockerfile multi-stage（builder 装依赖 → runtime 精简 + 非 root + healthcheck）
- deploy/k8s/ 七清单（探针 + 资源配额 + HPA）
- ADR 7 条 + 指标总报告 final_report.md

## 七、诚实边界（必须主动说明）

1. **无线上数据**：没有真实用户/流量，指标均为本地评测（合成语料 5 篇 + 真实引擎链路）
2. **检索提升未达标**：GraphRAG Recall@10 提升 -1.0%（目标 +8%），如实报告并给出解释（静态 embedding + 文档级判定口径）
3. **FC 准确率是静态代理指标**：真实 LLM 调用准确率需真实模式实测
4. **并发 65.6% 未达目标值 77.6%**：达标线 ≥60% 达成，目标值未达
5. **评测集为合成语料**：由 5 篇模拟企业文档构建，非真实企业数据

## 八、简历写法对照

| 简历条目 | 对应实现 | 可演示 |
|---|---|---|
| GraphRAG 检索（RRF + 一跳扩展 + 精排） | retrieval/ | /knowledge/search |
| 工具治理与执行域隔离 | tools/ + skills/ | /chat 触发工具 |
| Multi-Agent 编排 + checkpoint | agents/ | /agents/runs/{id} |
| 上下文工程与记忆 | context/ + memory/ | /memory/{user_id} |
| 全链路可观测 | observability/ | /traces/* |
| 指标评测 | eval/ | run_eval.py |
