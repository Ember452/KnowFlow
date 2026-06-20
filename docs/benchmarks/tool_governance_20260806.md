# 工具治理指标对比报告

> 生成时间: 2026-08-06 22:44:37
> 模式: 静态(规则意图识别, 无真实 LLM)
> 场景数: 33

## 指标总览

| 指标 | 全量注入(baseline) | 执行域隔离 | 下降率/准确率 | 目标 |
|---|---|---|---|---|
| 可见工具数(均值) | 6 | 3.39 | -43.4% | -34.2% |
| Schema Token(均值) | 504 | 276.24 | -45.2% | -32.6% |
| FC 准确率 | - | - | 100.0% | 94+% |

## 方法说明

- **全量注入(baseline)**: 忽略执行域隔离, 将全部非 internal 工具的 JSON Schema 注入 LLM prompt。
- **执行域隔离**: 按意图识别激活对应 Skill, 经 VisibilityCalculator 计算可见工具集(direct 恒可见 + skill_only 按激活 + subagent_only 按角色 + internal 永不可见)。
- **可见工具数**: 注入给 LLM 的工具定义数量, 越少 prompt 越精简。
- **Schema Token**: 注入 schema 的字符数 / 4 近似 Token 量。
- **FC 准确率**: 33 条场景中, 预期工具在隔离可见集中的比例(静态模式代理指标; 真实模式由 LLM 实际调用判定)。

## 场景明细

| 查询 | 角色 | 激活 Skill | 预期工具 | 可见工具数 | Token | FC 正确 |
|---|---|---|---|---|---|---|
| 公司报销流程是什么? | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| 产品 X 的规格参数 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| 请介绍一下年假政策 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| IT 故障申报流程 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| 财务报销审批节点 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| 产品手册有哪些功能 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| 运维手册的应急流程 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| HR 入职流程说明 | main | knowledge_qa | retrieval_tool | 2 | 150 | ✓ |
| 帮我算 2 的 10 次方 | main | data_analysis | calculator | 5 | 423 | ✓ |
| 计算 (1200 + 350) * 0.85 | main | data_analysis | calculator | 5 | 423 | ✓ |
| 把计算结果存成 CSV | main | data_analysis | file_write_tool | 5 | 423 | ✓ |
| 导出分析结果到文件 | main | data_analysis | file_write_tool | 5 | 423 | ✓ |
| 读取沙盒里的数据文件 | main | data_analysis | file_read_tool | 5 | 423 | ✓ |
| 列出工作区有哪些文件 | main | data_analysis | file_list_tool | 5 | 423 | ✓ |
| 算一下利润率 | main | data_analysis | calculator | 5 | 423 | ✓ |
| 查看 /workspace/result.json | main | data_analysis | file_read_tool | 5 | 423 | ✓ |
| 保存报告为 summary.md | main | data_analysis | file_write_tool | 5 | 423 | ✓ |
| 工作区文件清单 | main | data_analysis | file_list_tool | 5 | 423 | ✓ |
| 帮我总结产品手册核心功能 | main | document_summary | retrieval_tool | 3 | 251 | ✓ |
| 概括这份合同的要点 | main | document_summary | retrieval_tool | 3 | 251 | ✓ |
| 把摘要存成文件 | main | document_summary | file_write_tool | 3 | 251 | ✓ |
| 总结运维手册并导出 | main | document_summary | retrieval_tool | 3 | 251 | ✓ |
| 提取文档关键信息 | main | document_summary | retrieval_tool | 3 | 251 | ✓ |
| 生成结构化摘要文件 | main | document_summary | file_write_tool | 3 | 251 | ✓ |
| 审查 /workspace/snippet.py 的实现 | subagent | code_review | file_read_tool | 4 | 316 | ✓ |
| 这段代码符合最佳实践吗? 查一下规范 | subagent | code_review | search_tool | 4 | 316 | ✓ |
| 审查代码并搜索相关 API 文档 | subagent | code_review | search_tool | 4 | 316 | ✓ |
| 读取待审代码文件 | subagent | code_review | file_read_tool | 4 | 316 | ✓ |
| 查最新框架文档对照实现 | subagent | code_review | search_tool | 4 | 316 | ✓ |
| 你好, 自我介绍一下 | main | (none) | retrieval_tool | 2 | 150 | ✓ |
| 1+1 等于几 | main | (none) | calculator | 2 | 150 | ✓ |
| 知识库里有报销流程吗 | main | (none) | retrieval_tool | 2 | 150 | ✓ |
| 算 3*7 | main | (none) | calculator | 2 | 150 | ✓ |

## 结论

执行域隔离使可见工具数下降 **43.4%**(目标 34.2%), Schema Token 下降 **45.2%**(目标 32.6%), FC 准确率 **100.0%**(目标 94+%)。静态模式用规则意图识别模拟 Skill 激活, 真实模式请按 `docs/tests/指标测试-工具治理.md` 执行。

> 注: 静态模式 FC 准确率为「预期工具在可见集中」的代理指标, 不等同真实 LLM 调用准确率。真实模式需 LLM API Key, 由 ToolOrchestrator 跑完整工具调用循环后统计。
