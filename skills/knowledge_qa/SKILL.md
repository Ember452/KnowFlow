---
name: knowledge_qa
description: 企业知识库问答技能，激活知识检索工具链，基于 GraphRAG 召回相关片段作答
domain: skill_only
tools:
  - retrieval_tool
dependencies:
  - retrieval_tool
enabled: true
---

# 知识问答技能

当用户提出知识查询类问题（如公司制度、产品参数、流程规范）时激活此技能。
通过 `retrieval_tool` 检索企业知识库，返回相关文档片段并据此生成答案，标注来源引用。

## 适用场景

- "公司报销流程是什么？"
- "产品 X 的规格参数"
- "请介绍一下年假政策"

## 工具链

1. `retrieval_tool`：GraphRAG 检索（向量 + BM25 混合召回 + 一跳扩展 + 精排）
