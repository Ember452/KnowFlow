---
name: data_analysis
description: 数据分析技能，激活计算器与沙盒文件工具，支持数值计算与结果导出
domain: skill_only
tools:
  - calculator
  - file_read_tool
  - file_write_tool
  - file_list_tool
dependencies: []
enabled: true
---

# 数据分析技能

当用户需要进行数值计算、数据处理或导出分析结果时激活此技能。
通过 `calculator` 求值数学表达式，用文件工具读写沙盒中的数据文件。

## 适用场景

- "帮我算 2 的 10 次方"
- "计算 (1200 + 350) * 0.85"
- "把计算结果存成 CSV"

## 工具链

1. `calculator`：安全数学表达式求值
2. `file_read_tool`：读取沙盒数据文件
3. `file_write_tool`：写出分析结果到沙盒
4. `file_list_tool`：列出沙盒已有文件
