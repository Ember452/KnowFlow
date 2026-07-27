# KnowFlow

> 企业知识库 Agent 平台：混合检索 + 工具治理 + Multi-Agent 编排。
> 面向 Agent 开发岗位的真实可运行项目 —— 五个核心指标全部有实测数据支撑。

## 项目简介

KnowFlow 是一个可编排、可扩展的企业知识库 Agent 平台，覆盖从**文档索引 → 混合检索 → 工具调用 → 多 Agent 任务编排 → 全链路可观测**的完整闭环：

- **混合检索**：向量 + BM25 双路召回（RRF 融合）、本地 reranker 精排、向量异常自动降级 BM25
- **工具治理与 Skill 体系**：四类执行域隔离（direct/skill_only/subagent_only/internal）、可见工具数下降 43.4%、Schema Token 下降 45.2%
- **Multi-Agent 编排**：LangGraph 状态机（understand → plan → delegate → execute → summarize）、asyncio 并发委派（较串行耗时下降 65.6%）、checkpoint 断点续跑
- **上下文工程与记忆**：token 预算/窗口/摘要/卸载策略、Redis 短期记忆 + PG 长期记忆分层
- **可观测与评测**：全链路 Trace（嵌套 span + replay）、统一评测入口、指标可复现

## 架构

```
┌──────────────────────────────────────────────────────────────┐
│                         客户端层                              │
│              Web / API Client / SSE Stream                    │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────┐
│                    API 网关层（FastAPI）                      │
│  路由 · 鉴权 · 租户隔离 · SSE 流式 · Trace 注入 · 限流        │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                  Agent 编排层（LangGraph）                    │
│  主 Agent ──task 委派──▶ 子 Agent（子线程隔离上下文）         │
│  checkpoint 父子关系 · 并发执行 · 可观测追踪 · 状态机         │
└──┬──────────┬──────────┬──────────┬──────────┬───────────────┘
   │          │          │          │          │
┌──▼──┐   ┌───▼───┐  ┌───▼────┐ ┌───▼────┐ ┌───▼────────┐
│混合  │   │工具治理│  │上下文  │ │沙盒    │ │流式+可观测 │
│检索  │   │模块   │  │工程    │ │文件系统│ │+记忆       │
│模块  │   │       │  │模块    │ │模块    │ │模块        │
└──┬──┘   └───┬───┘  └───┬────┘ └───┬────┘ └───┬────────┘
   │          │          │          │          │
┌──▼──────────▼──────────▼──────────▼──────────▼───────────────┐
│                        存储层                                 │
│  Milvus(向量) · PostgreSQL(业务) · MinIO(文件)           │
│  Redis(会话+记忆)                                            │
└──────────────────────────────────────────────────────────────┘
```

## 技术栈

| 层级 | 技术 |
|---|---|
| 语言/包管理 | Python 3.13 + uv |
| Web | FastAPI + SSE 流式 |
| Agent | LangGraph + LangChain |
| 检索 | Milvus（向量）+ BM25 + 本地 reranker 精排 |
| 存储 | PostgreSQL / Redis / MinIO |
| 工具协议 | MCP（Model Context Protocol） |

## 快速开始（3 步起服务）

```bash
# 1. 安装依赖
uv sync

# 2. 启动依赖容器并初始化（PostgreSQL / Redis / MinIO / Milvus）
make up && make init-db && make init-milvus

# 3. 启动 API 服务（另开终端启动索引 Worker: make worker）
make dev
```

> Windows PowerShell 用户：命令分隔用 `;`，不要使用 `&&`。

### 首次使用前

1. 复制 `.env.example` 为 `.env`，填写 `KNOWFLOW_LLM_API_KEY`（评测与演示建议用 deepseek-chat 等低价模型）
2. 上传文档并索引：
   ```bash
   curl -X POST http://localhost:8000/api/v1/documents/upload -F "file=@docs/README.md"
   ```
3. 验证服务：`curl http://localhost:8000/health` → `{"status": "ok"}`

## 核心能力演示

### 1. 知识问答（检索增强 + 流式 + 引用）

```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "员工年假制度是什么？"}'
```

### 2. 工具调用与执行域隔离

```bash
# 触发 calculator 工具（data_analysis Skill 激活）
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "帮我算 2 的 10 次方"}'
```

### 3. Multi-Agent 委派并发执行

```bash
# 对比类问题 → 复杂任务 → 委派多个子 Agent 并发执行后汇总
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" \
  -d '{"user_id": "demo", "message": "对比产品 A/B/C 的价格与参数并汇总"}'

# 查看父子 run 与委派链（状态机可见性）
curl http://localhost:8000/api/v1/agents/runs/1
```

### 4. 全链路 Trace 与 Replay

```bash
curl http://localhost:8000/api/v1/traces/1            # 嵌套 span 树
curl http://localhost:8000/api/v1/traces/stats        # 聚合统计
curl -X POST http://localhost:8000/api/v1/traces/replay \
  -d '{"session_id": 1}'                              # checkpoint + trace 重放
```

## 指标总览（实测）

| 指标 | 实测 | 目标 | 报告 |
|---|---|---|---|
| GraphRAG Recall@10 提升 | -1.0%（静态模式，未达目标） | ≥ +8% | [compare_20260608.md](eval/reports/compare_20260608.md) |
| 可见工具数下降 | **-43.4%** | -34.2% | [tool_governance_20260807.md](docs/benchmarks/tool_governance_20260807.md) |
| Tool Schema Token 下降 | **-45.2%** | -32.6% | 同上 |
| FC 准确率 | **100.0%**（静态代理） | ≥ 94% | 同上 |
| 并发较串行耗时下降 | **65.6%**（最佳 84.1%） | ≥ 60% | [multiagent_20260807.md](docs/benchmarks/multiagent_20260807.md) |

完整口径与诚实边界见 [eval/reports/final_report.md](eval/reports/final_report.md)。

## 工程门禁

```bash
make lint          # ruff check
make format-check  # ruff format --check
make type          # mypy
make test-unit     # pytest tests/unit（覆盖率 ≥60%，核心模块 ≥70%）
make pre-commit    # pre-commit 全部 hook
```

## 文档索引

| 文档 | 说明 |
|---|---|
| [项目设计文档](docs/KnowFlow-项目设计文档.md) | PRD / 架构 / 模块设计 / 面试叙事 |
| [项目结构](docs/KnowFlow-项目结构.md) | 目录分层规范 |
| [开发计划](docs/KnowFlow-开发计划.md) | P0-P11 阶段任务与验收标准 |
| [architecture.md](docs/architecture.md) | 系统架构详解 |
| [api_reference.md](docs/api_reference.md) | API 参考（含示例） |
| [skill_development.md](docs/skill_development.md) | 如何开发一个新 Skill |
| [deployment.md](docs/deployment.md) | docker-compose / k8s 部署说明 |
| [interview_story.md](docs/interview_story.md) | 面试叙事与追问应答 |
| [ADR](docs/adr/) | 架构决策记录（7 条） |
| [指标总报告](eval/reports/final_report.md) | 五个核心指标实测汇总 |

## License

MIT
