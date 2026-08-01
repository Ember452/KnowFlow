# ADR 0010: 前端 Demo 用 React + Vite，构建产物由后端托管

- 状态: Accepted
- 日期: 2026-08-10
- 关联: 《KnowFlow-前端Demo设计文档》二、技术选型与取舍

## Context

后端能力（检索/工具治理/多 Agent 编排/记忆/可观测/报告流水线/飞书发布）已完整，
需要前端 Demo 做过程可视化（尤其 Agent 编排），并保证"功能按钮齐全、一条命令可演示"。

候选方案：
- React 18 + Vite + TS + Tailwind + ReactFlow：Agent 流程图生态最成熟（节点/边/状态着色），
  面试叙事友好；代价是包体积大于 Vue/原生（页面级 lazy 缓解）。
- Vue 3 + Vite + vue-flow：上手快，生态略弱。
- 原生 HTML/JS：零依赖零构建，但 Agent 可视化需自绘 SVG，代码量大、难维护。

部署形态：前端独立部署（前后端分离，工程化叙事好但演示需两进程）vs
构建产物由 FastAPI StaticFiles 托管（单端口一条命令起全栈，Demo 演示最顺）。

## Decision

**前端用 React 18 + Vite 5 + TypeScript + TailwindCSS，Agent 流程图用 ReactFlow**；
**构建产物 `web/dist` 由 FastAPI 静态托管（同端口 8000）**，开发时 Vite dev server 代理
`/api` 到 8000。SSE（POST /chat/stream）用 fetch + ReadableStream 解析，不改后端。

## Consequences

正面:
- Agent 编排可视化落地快: ReactFlow 节点/边/状态着色开箱即用, 事件驱动四面板联动.
- 演示成本最低: 单端口单进程, 上传文档→问答→Agent 编排→报告→飞书发布一条链路.
- 前后端契约明确: TS 类型对齐后端 schema, 接口演进编译期暴露.
- 前端独立演进: 开发热更新与生产托管互不影响.

负面:
- React+ReactFlow 包体积较大, 需页面级 lazy 加载控制首屏.
- 新增 Node 工具链(与 uv 生态并存, 前端依赖由 npm 管理).
- 生产无独立前端进程(多租户/独立部署场景需改造, Demo 场景不需要).
