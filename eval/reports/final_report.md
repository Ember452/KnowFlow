# KnowFlow 指标总报告（final_report）

> 生成时间：2026-08-07
> 说明：本报告汇总 P3/P6/P8 三个 benchmark 脚本的实测结果与检索评测对比。**所有数值均为真实运行产物**（报告文件为证据），静态模式与真实模式的口径在对应章节如实标注。

## 核心指标总览

| 指标 | 实测 | 目标 | 数据来源 |
|---|---|---|---|
| GraphRAG Recall@10 提升 | **-1.0%**（静态模式，未达目标） | ≥ +8% | [compare_20260608.md](../eval/reports/compare_20260608.md) |
| 可见工具数下降 | **-43.4%** | -34.2% | [tool_governance_20260807.md](../docs/benchmarks/tool_governance_20260807.md) |
| Schema Token 下降 | **-45.2%** | -32.6% | [tool_governance_20260807.md](../docs/benchmarks/tool_governance_20260807.md) |
| FC 准确率 | **100.0%**（静态代理指标） | ≥ 94% | [tool_governance_20260807.md](../docs/benchmarks/tool_governance_20260807.md) |
| 并发较串行耗时下降 | **65.6%**（均值，最佳 84.1%） | ≥ 60%（目标值 77.6%） | [multiagent_20260807.md](../docs/benchmarks/multiagent_20260807.md) |

## 检索效果：GraphRAG vs Hybrid

**报告**：[compare_20260608.md](../eval/reports/compare_20260608.md)（静态模式，合成语料 5 篇 43 块 + fake embedding 的完整引擎链路）

- 评测集：50 条查询（direct 15 / cross_doc 20 / semantic 15）
- 总体：Hybrid Recall@10 33.6% / GraphRAG 32.6%（**-1.0%**）；MRR 0.6592 → 0.6804（+0.0213）
- 分组：跨文档查询 Recall +0.5%、MRR 0.8000 → 0.8667（GraphRAG 一跳扩展在跨文档场景有正向收益）
- **诚实边界**：静态模式使用 hashing embedding（非 bge-m3）与词项重叠精排（非 cross-encoder），且相关 chunk 判定为文档级展开，Recall 数值整体偏低；**+8% 目标未达成**，真实模型链路按 `docs/tests/指标测试-检索.md` 执行后再更新本表
- 复用验证：`uv run python eval/scripts/compare_baseline.py`

## 工具治理：执行域隔离收益

**报告**：[tool_governance_20260807.md](../docs/benchmarks/tool_governance_20260807.md)（静态模式，规则意图识别 + 33 个场景）

- 可见工具数：全量注入 6 → 执行域隔离 3.39（**-43.4%**，目标 -34.2%）
- Schema Token：504 → 276.24（**-45.2%**，目标 -32.6%）
- FC 准确率：**100.0%**（目标 ≥94%）
- **口径说明**：静态模式 FC 为「预期工具在隔离可见集中的比例」代理指标；真实 LLM 调用准确率需 `uv run python scripts/benchmark_tools.py --mode real`
- 复用验证：`uv run python scripts/benchmark_tools.py`（另有 20260806 版本见 docs/benchmarks/）

## Multi-Agent 并发编排

**报告**：[multiagent_20260807.md](../docs/benchmarks/multiagent_20260807.md)（静态模式，真实并发执行器 run_concurrent + 模拟子任务延迟 1.2-2.2s）

- 并发较串行耗时下降：均值 **65.6%**，最佳 **84.1%**（2/3/5/8 子任务四组场景）
- 目标 ≥60% 达成；目标值 77.6% 未达（2 子任务场景仅 42.5%，随子任务数增加趋近理论值）
- 理论下降率与实测一致（调度开销可忽略）
- 复用验证：`uv run python scripts/benchmark_multiagent.py`

## QA 与统一评测入口

- 评测集：`eval/datasets/knowledge_qa_eval.jsonl`（60 条 QA，要点标注取自语料原文）、`retrieval_eval.jsonl`（50 条）
- 统一入口：`uv run python eval/scripts/run_eval.py --all`（静态流程验证）或 `--mode real --all`（真实 LLM + 真实检索，需外部依赖，按 `docs/tests/` 测试文档执行）
- 产出：`eval/reports/retrieval_report_{mode}.md` / `qa_report_{mode}.md` / `tool_fc_report_{mode}.md`

## 结论与面试口径

1. **五个指标中四个达标或超目标**（工具数 -43.4%、Schema Token -45.2%、FC 100%、并发 65.6%），**检索提升 -1.0% 未达 +8% 目标**——如实呈现，静态口径下跨文档场景已现正向趋势（MRR +0.0213）
2. 静态模式保证结果可复现（无 LLM/模型依赖），真实模式口径已在各报告标注
3. 全部数值可追溯至 benchmark 脚本与报告文件，无手工编造数据
