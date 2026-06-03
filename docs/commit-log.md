# KnowFlow 提交日志

> 本项目全部 git commit 的时间线与信息记录，用于保持 GitHub 提交历史与简历时间线一致。
> 规则：时间线起点为 **2026 年 6 月初**（首条记录从 2026-06-01 开始）；后续批次的日期必须**晚于最后一条记录**（向后推迟，同一批次多条可分布在相邻日期，按提交顺序递增）。

## 记录格式

```
YYYY-MM-DD | <type>(<scope>): <subject>
```

## 提交记录

2026-06-01 | chore: 初始化项目元文件与 git 忽略规则
2026-06-01 | build: 编写 pyproject.toml 与运行时依赖声明
2026-06-01 | build: 添加 docker-compose 与工程化配置
2026-06-01 | docs: 添加项目设计文档与开发规范
2026-06-01 | chore(core): 创建 src 包目录骨架与冒烟测试
2026-06-02 | feat(core): 实现应用配置与 pydantic-settings 加载
2026-06-02 | feat(core): 定义全局常量与异常体系
2026-06-02 | feat(core): 接入 structlog 结构化日志
2026-06-02 | feat(core): 添加生命周期管理与 OpenTelemetry 钩子
2026-06-02 | feat(db): 接入 PostgreSQL/Redis/Milvus/MinIO 客户端
2026-06-02 | feat(api): 添加 FastAPI 应用工厂与依赖检查脚本
2026-06-03 | docs(adr): 记录 checkpoint 存储决策
2026-06-03 | feat(db): 实现 ORM 基类与全部领域模型
2026-06-03 | feat(db): 配置 Alembic 异步迁移与初始 schema 迁移
2026-06-03 | feat(scripts): 添加数据库初始化脚本
2026-06-03 | feat(db): 实现 Document/Chunk 与图谱 Repository 及单测
2026-06-03 | feat(db): 实现会话/Agent/Trace Repository 及单测
