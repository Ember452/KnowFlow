---
name: code_review
description: 代码审查专家技能，仅子 Agent 可见，结合网络搜索与沙盒文件读取进行代码评审
domain: subagent_only
tools:
  - search_tool
  - file_read_tool
dependencies:
  - search_tool
enabled: true
---

# 代码审查技能

仅子 Agent 可激活的专家技能。通过 `search_tool` 查询最佳实践与 API 文档，
用 `file_read_tool` 读取沙盒中的待审代码文件，输出审查意见。

## 适用场景

- "审查 /workspace/snippet.py 的实现"
- "这段代码是否符合最佳实践？查一下相关规范"

## 工具链

1. `search_tool`：网络搜索最佳实践/官方文档（subagent_only）
2. `file_read_tool`：读取沙盒中的代码文件
