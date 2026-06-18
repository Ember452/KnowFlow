---
name: document_summary
description: 文档摘要技能，检索文档片段并生成结构化摘要，可导出摘要文件到沙盒
domain: skill_only
tools:
  - retrieval_tool
  - file_write_tool
dependencies:
  - retrieval_tool
enabled: true
---

# 文档摘要技能

当用户要求总结/概括某主题或文档时激活此技能。先检索相关片段，再生成结构化摘要，
可通过 `file_write_tool` 将摘要导出为沙盒文件供下载。

## 适用场景

- "帮我总结一下产品手册的核心功能"
- "概括这份合同的要点"
- "把摘要存成文件"

## 工具链

1. `retrieval_tool`：检索待摘要的文档片段
2. `file_write_tool`：将摘要写入 `/workspace/summary.md`
