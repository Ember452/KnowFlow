# KnowFlow Web 前端

企业知识库 Agent 平台前端，与后端 `src/knowflow` 平级，互不影响。

## 技术栈

React 18 + TypeScript + Vite 5 + Ant Design 5 + zustand 4

## 快速开始

```bash
cd web
npm install
npm run dev        # 开发服务器 http://localhost:5173
```

后端需运行在 `http://localhost:8000`，Vite 已配置 `/api` 代理转发。

如后端地址不同，创建 `.env.local`：

```
VITE_API_BASE=http://your-host:8000/api/v1
```

## 构建

```bash
npm run build      # tsc 类型检查 + vite build → dist/
npm run preview    # 预览构建产物
npm run typecheck  # 仅类型检查
```

## 页面清单

| 路由 | 页面 | 功能 |
|---|---|---|
| `/dashboard` | 总览 | 五大量化指标、服务健康、对话脉搏、模块入口 |
| `/chat` | 智能对话 | SSE 流式问答、检索片段展示、工具调用时间线、引用溯源 |
| `/knowledge` | 知识库 | 文档上传(拖拽)、异步索引状态(自动轮询)、检索测试 |
| `/graph` | 知识图谱 | 实体关系力导向可视化、悬停高亮邻居、关系方向与类型展示 |
| `/retrieval` | 检索调试 | GraphRAG 全链路可视化(召回→融合→扩展→精排)、来源分布、实体命中 |
| `/agents` | Agent 编排 | 父子 Run 树、委派链、Checkpoint 血缘、并发可视化 |
| `/tools` | 工具治理 | Skill 启停、执行域分布、工具调用指标(成功率/延迟/Token) |
| `/memory` | 记忆 | 长期记忆列表、沉淀触发、重要度展示 |
| `/observability` | 可观测 | Trace span 树(点击看输入/输出)、24h 统计、会话 Replay |
| `/eval` | 评测 | Baseline vs GraphRAG 对比、指标提升幅度、运行历史 |
| `/sandbox` | 沙箱 | 会话工作区文件、配额进度、卸载文件标记 |
| `/system` | 系统 | 存活/就绪探针、依赖状态、技术栈、API 端点清单 |

## 目录结构

```
web/
├── src/
│   ├── api/           # 9 个 API 模块 + SSE 流式客户端
│   ├── components/    # 共享组件(PageHeader / StatCard / StatusTag / EmptyState)
│   ├── config/        # 侧边栏导航配置
│   ├── hooks/         # useAsync 数据获取 hook
│   ├── layouts/       # 主布局(侧边栏 + 顶栏)
│   ├── lib/           # 格式化工具(字节/毫秒/百分比/时间)
│   ├── pages/         # 12 个功能页面
│   ├── router/        # 路由配置
│   ├── stores/        # zustand 状态管理(appStore / chatStore)
│   ├── styles/        # AntD 主题(Claude 设计系统 token 映射)
│   ├── generated/     # 由 openapi.json 自动生成的 API 端点清单
│   └── types/         # TypeScript 类型定义(对齐后端 models)
├── vite.config.ts     # Vite 配置(含 /api 代理)
└── package.json
```

## 设计系统

采用 Claude 设计系统 token 映射到 AntD v5 主题：

- 主色：`#C96442`(亮) / `#D97757`(暗) — 温暖的 terracotta
- 背景：`#FAF9F5` 暖纸感
- 圆角：8px / 12px
- 字体：Poppins(UI) + Newsreader(展示)

支持亮/暗模式切换（顶栏灯泡开关），暗色模式通过 CSS 语义变量（`--kf-surface-tint` 等）整体切换。

## 质量门禁

```bash
npm run typecheck   # tsc 严格类型检查
npm run lint        # ESLint (typescript-eslint + react-hooks)
npm run build       # prebuild 自动从 openapi.json 生成 API 清单 → 构建
```

对话“停止”按钮通过 `AbortController` 真正中断 SSE 连接（后端 `request.is_disconnected` 同步取消生成器）；
工具调用展示通过后端 `call_id` 精确关联 `tool_start`/`tool_end`。
