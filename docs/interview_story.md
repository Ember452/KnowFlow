# KnowFlow 面试叙事

> 基于设计文档"四、面试核心叙事"扩写：每个指标的故事线 + 可能的追问与应答。
> **诚实边界**：所有指标为本地评测（合成语料 + 静态/真实双模式），无线上数据——被追问时如实说明。

## 一句话定位

> "KnowFlow 是一个企业知识库 Agent 平台，解决四个工程问题：检索召回（混合检索）、工具调用治理（执行域隔离）、复杂任务编排（Multi-Agent）、上下文治理（卸载 + 摘要）。每个问题都有实测指标支撑。"

## 叙事主线

**不是简单的 RAG 问答，而是企业级 Agent 平台**。从 P0 到 P11 按里程碑推进：底座 → 混合检索 → API → 对话 → 工具 → 上下文/记忆 → 多 Agent → 评测收尾。关键决策都有取舍逻辑（ADR 5 条）。

## 一、混合检索（指标：Recall@10 33.6%）

### 故事线

- 单路检索的局限：纯向量对关键词不敏感、纯关键词无法理解语义（如"年假制度"在 HR 文档里可能写作"休假规则"）
- 方案：向量 + BM25 双路召回，RRF 融合（k=60）→ 本地 reranker 精排；索引侧向量/BM25 双写，重建一致性可验证
- 降级：向量库或 embedding 服务异常且未强制要求时，自动降级本地 BM25 + hybrid_score reranker，对话不中断
- 评测：50 条查询分三类（直接/跨文档/语义），静态模式（可复现）与真实模式（真实模型）双口径

### 追问与应答

**Q：为什么用 RRF 融合，不用加权分数相加？**
A：向量相似度与 BM25 分数量纲不同、分布差异大，直接加权需要调权重且不稳定；RRF 只依赖排名（1/(k+rank)），跨路可比，k=60 是经典平滑参数。

**Q：向量召回和 BM25 各自解决什么问题？**
A：向量解决语义同义（"休假" vs "年假"），BM25 解决精确词与编号（SLA 编号、产品型号），双路互补；融合后单路不足时另一路保底。

**Q：向量库异常时怎么降级？**
A：Chroma/embedding 不可用且 `KNOWLEDGE_VECTOR_REQUIRED=false` 时，自动回退本地 BM25 + `hybrid_score` reranker，检索链路不中断；强制要求向量时显式报错暴露问题。

**Q：指标具体是多少？怎么测的？**
A：静态模式（合成语料 5 篇 43 块 + hashing embedding 的完整引擎链路）Recall@10 33.6%、MRR 0.6592（精排后 0.6804）。**诚实说明**：静态口径 embedding 非真实模型；真实模型链路按 `docs/tests/指标测试-检索.md` 执行后更新。

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

## 三、Multi-Agent 编排（指标：并发 -77.6%，子 Agent 工具化）

### 故事线

- 痛点：复杂任务（对比 A/B/C、写报告、多主题调研）串行执行慢；子 Agent 若只是"换个 prompt 再调一次 LLM"，多 Agent 就没有存在价值
- 方案：LangGraph 状态机（understand → plan → delegate → execute → summarize），主 Agent 规划拆解，子 Agent 独立上下文并发执行
- **子 Agent 工具化（核心亮点）**：子 Agent 复用 ToolOrchestrator 以 SUBAGENT 角色跑工具循环——`subagent_only` 域工具（code_review / report_writing 技能）仅子 Agent 可见，主 Agent 看不到也调不到；规划 prompt 注入子 Agent 可用工具清单，主 Agent 据此拆出"能被执行"的任务
- 子任务按需检索：各子任务用自己的文本检索知识库，不共享主 Agent 预检索上下文（跨主题不串扰）
- 可观测：子 Agent 每次工具调用以 tool_start/tool_end 事件经 SSE 上抛（带 subtask_id 标注来源），前端可见"哪个子 Agent 调了什么工具"；工具调用记录随 SubtaskInfo 落库
- 并发：asyncio.gather + 超时（60s）+ 降级（单子失败不阻塞）
- checkpoint：站在 LangGraph 肩上用 PostgresSaver 原生表（ADR 0004），thread_id = run_id，lineage 沿 parent_checkpoint_id 回溯，断点续跑
- 效果：并发较串行耗时下降均值 **65.6%**（最佳 84.1%），目标 ≥60%

### 追问与应答

**Q：为什么用 LangGraph 而不是自己写状态机？**
A：状态机模型（节点 + 条件路由）天然适配多步推理；原生 checkpoint 支持断点续跑，序列化协议（channel versions/writes）是成熟实现，自己写容易出错（ADR 0004 的 Context 部分有完整论证）。

**Q：子 Agent 和主 Agent 的区别？只是多调一次 LLM 吗？**
A：不是。子 Agent 以 SUBAGENT 角色跑完整工具循环：可见 subagent_only 域工具集（主 Agent 不可见）、独立检索上下文、独立 system prompt（工具型提示词）、工具调用经 on_tool 上抛可观测。执行域隔离的 subagent_only 域就是为这个设计的——注入的工具随角色变化，同一套 Skill 体系同时约束主/子两方。

**Q：主 Agent 怎么知道子 Agent 能干什么？**
A：规划 prompt 注入子 Agent 可见工具清单（ToolOrchestrator.visible_tools_text 按 SUBAGENT 角色计算），主 Agent 据此拆任务——工具不可达的需求不会拆成子任务，避免"拆了也干不了"。

**Q：子 Agent 工具调用怎么展示？**
A：SSE 事件流逐条转发 tool_start/tool_end（含 subtask_id），前端可区分事件来自哪个子 Agent；同时记录在子任务结果里，会话 replay 可见。

**Q：子 Agent 之间上下文隔离怎么做？**
A：子 Agent 只看自己的任务描述 + 按需检索结果，不注入主 Agent 完整历史；各自挂独立 ContextManager 实例（窗口/预算策略互不影响）。

**Q：断点续跑演示过吗？**
A：有（docs/demo_checkpoint.md）：kill 进程后以同一 thread_id + checkpoint_id 调 graph.ainvoke，LangGraph 恢复 channel 状态继续执行；委派里程碑 checkpoint 存在 task_delegations.checkpoint_id 可精确定位。

**Q：子任务失败了怎么办？**
A：降级——单子失败标记 failed 不阻塞其他子任务，汇总时如实标注"该部分未能获取"；主 run 仍 completed。子 Agent 输出还有质量门禁（<20 字符视为无效）+ 携带原因重试 1 次。

**Q：为什么 2 子任务场景下降只有 42.5%，不到 77.6%？**
A：77.6% 是目标值，均值 65.6% 达标（≥60%）。子任务数越多并发收益越接近理论值（8 子任务 84.1%），2 子任务时调度开销占比高。**诚实说明**：静态模式是模拟延迟，真实模式受 LLM 网络波动影响；子 Agent 工具化链路（真实 LLM + 真实工具调用）按测试文档执行后更新。

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
2. **检索指标为静态口径**：混合检索 Recall@10 33.6%（静态 embedding + 文档级判定口径），真实模型口径待实测
3. **FC 准确率是静态代理指标**：真实 LLM 调用准确率需真实模式实测
4. **并发 65.6% 未达目标值 77.6%**：达标线 ≥60% 达成，目标值未达
5. **评测集为合成语料**：由 5 篇模拟企业文档构建，非真实企业数据

## 八、简历写法对照

| 简历条目 | 对应实现 | 可演示 |
|---|---|---|
| 混合检索（向量+BM25 RRF 融合 + 精排） | retrieval/ | /knowledge/search |
| 工具治理与执行域隔离 | tools/ + skills/ | /chat 触发工具 |
| Multi-Agent 编排 + checkpoint | agents/ | /agents/runs/{id} |
| 上下文工程与记忆 | context/ + memory/ | /memory/{user_id} |
| 全链路可观测 | observability/ | /traces/* |
| 指标评测 | eval/ | run_eval.py |
