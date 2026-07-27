---
name: report_writing
description: 报告撰写专家技能，仅子 Agent 可见，结合知识检索、数值计算与沙盒文件工具完成调研报告
domain: subagent_only
tools:
  - retrieval_tool
  - calculator
  - file_read_tool
  - file_write_tool
  - file_list_tool
dependencies:
  - retrieval_tool
enabled: true
---

# 报告撰写技能

仅子 Agent 可激活的专家技能。通过 `retrieval_tool` 检索知识库素材，
用 `calculator` 处理数据口径，将成稿写入沙盒 `/workspace/` 供主 Agent 汇总。

## 适用场景

- "撰写新品上市分析报告的某章节"
- "整理某主题的调研素材并输出要点"
- "汇总多个数据口径并生成结论段"

## 工具链

1. `retrieval_tool`：混合检索（向量 + BM25 双路召回 + RRF 融合 + 精排）
2. `calculator`：安全数学表达式求值（数据口径计算）
3. `file_read_tool`：读取沙盒中已有素材
4. `file_write_tool`：报告成稿写入沙盒
5. `file_list_tool`：列出沙盒已有文件
