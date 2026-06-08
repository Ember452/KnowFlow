# KnowFlow 产品手册

## 1. 产品概述

KnowFlow 是企业知识库 Agent 平台, 支持知识检索、多轮对话、工具调用与任务编排. 基于 LangGraph 编排引擎, 集成 MCP 协议, 可扩展自定义工具.

## 2. 核心功能

### 2.1 知识检索

KnowFlow 采用 GraphRAG 检索架构, 包含以下能力:

- 文档解析: 支持 PDF、DOCX、Markdown、纯文本四种格式
- 分块策略: 递归字符分块, 默认 chunk_size=512, overlap=64
- 混合检索: 向量召回(BAAI/bge-m3)与 BM25 召回双路融合, RRF 融合参数 k=60
- 一跳扩展: 通过实体关系图谱扩展关联分块, 提升召回率
- 精排: cross-encoder(BAAI/bge-reranker-v2-m3)对候选结果二次排序

### 2.2 Agent 编排

基于 LangGraph 实现 Agent 编排, 支持以下能力:

- 主 Agent 负责意图识别与任务委派
- 子 Agent 处理特定域任务, 通过 Skill 激活
- 工具调用遵循 MCP 协议, 支持直接域、技能域、子代理域、内部域四种可见性
- 最大工具调用轮数 5 轮, 防止死循环

### 2.3 上下文管理

- 上下文预算: 默认 32000 tokens
- 溢出阈值: 4000 tokens, 触发记忆沉淀
- 短期记忆存 Redis, 长期记忆沉淀至 PostgreSQL

## 3. 技术架构

KnowFlow 后端基于 FastAPI 构建, 数据层使用 PostgreSQL(元数据)、Milvus(向量)、Redis(缓存)、MinIO(文件存储).

## 4. 部署方式

支持 Docker Compose 本地部署与 Kubernetes 集群部署. 本地开发使用 `docker compose up -d` 启动全部依赖.

## 5. 配置管理

全部配置通过环境变量管理, 前缀 `KNOWFLOW_`. 关键配置项包括 LLM API Key、Embedding 模型路径、数据库连接串等.
