# KnowFlow

> 企业知识库 Agent 平台：GraphRAG 检索 + 工具治理 + Multi-Agent 编排。
> 面向 Agent 开发岗位面试的真实可运行项目。

## 技术栈

- **语言/包管理**：Python 3.13 + uv
- **Web**：FastAPI + SSE 流式
- **Agent**：LangGraph + LangChain
- **检索**：Milvus（向量）+ PostgreSQL（图谱）+ BM25
- **存储**：PostgreSQL / Redis / MinIO

## 快速开始

> 完整文档将在 P11 阶段补全。当前处于 M1（脚手架 + 基础设施 + 数据模型）阶段。

```bash
# 1. 安装依赖
uv sync

# 2. 启动本地依赖容器
make up

# 3. 初始化数据库
make init-db

# 4. 启动开发服务器
make dev
```

## 项目结构

详见 [docs/KnowFlow-项目结构.md](docs/KnowFlow-项目结构.md)。

## 开发计划

详见 [docs/KnowFlow-开发计划.md](docs/KnowFlow-开发计划.md)。

## License

MIT
