---
name: report_publish
description: 报告发布专家技能，激活后可调用飞书 MCP 工具将报告写入用户飞书云文档
domain: skill_only
tools:
  - mcp_feishu_create_doc
  - mcp_feishu_append_to_doc
  - mcp_feishu_update_doc
dependencies: []
enabled: true
---

# 报告发布技能

报告生成完成后激活的专家技能。通过飞书 MCP 工具链创建云文档、
分章节写入报告正文并返回文档链接。

## 适用场景

- 深度研究报告一键发布到飞书云文档
- 知识库总结报告写入用户云文档
- 报告更新后追加新版本内容

## 工具链

1. `mcp_feishu_create_doc`：创建飞书云文档（标题 + 可选正文），返回 doc_token 与链接
2. `mcp_feishu_append_to_doc`：向云文档末尾追加章节正文（分章节写入）
3. `mcp_feishu_update_doc`：追加【更新】版本（重复发布时幂等更新）

## 使用说明

- 发布动作只在报告完成、本 Skill 激活时可见，普通问答场景不可见（skill_only 域隔离）；
- 未配置飞书凭证时工具调用返回可读降级提示，报告仍可从沙盒获取，不影响生成链路。
