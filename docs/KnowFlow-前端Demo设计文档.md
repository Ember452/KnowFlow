# KnowFlow 前端 Demo 设计文档

> 版本：v1.0　日期：2026-08-10
> 配套：《KnowFlow 项目设计文档》（后端能力）《KnowFlow-项目结构.md》（目录）《开发计划》P12/P13（报告/飞书）
> 决策记录：`docs/adr/0010-web-frontend-stack.md`

---

## 一、背景与目标

KnowFlow 后端已具备全链路能力（混合检索 / 工具治理 / Multi-Agent 编排 / 上下文工程 / 记忆 / 沙盒 / 可观测 / 报告流水线 / 飞书发布），但当前只有 API 与 curl 演示，**过程不可见**——尤其多 Agent 编排的委派、子任务、工具调用、checkpoint 链路无法直观展示，面试与演示说服力受限。

本前端 Demo 的目标：

1. **功能按钮齐全**：覆盖后端全部 26 个 API 路径（22 既有 + 4 报告），每个能力都有可操作的入口；
2. **Agent 调用详细可视化**（核心诉求）：多 Agent 编排的状态机流转、子任务委派链、工具调用记录、SSE 事件时间线、Trace 树、报告六阶段流水线，全部实时可视化；
3. **知识库等能力完整**：文档管理、检索测试、Skill 启停、记忆管理、评测中心；
4. **演示流畅**：构建产物由 FastAPI 托管（同端口 8000），一条命令起全栈。

**目标用户**：面试官 / 演示者（主导航可直达每个能力页，均有预置示例输入降低演示门槛）。

## 二、技术选型与取舍

| 决策 | 选择 | 理由 | 取舍 |
|---|---|---|---|
| 框架 | React 18 + Vite 5 + TypeScript | 生态最强；Agent 流程图用 ReactFlow 成熟方案 | 包体积大于 Vue（按需加载缓解） |
| 样式 | TailwindCSS 3 | 快速搭建控制台风格，无样式文件碎片 | 类名冗长（可接受） |
| 可视化 | ReactFlow（流程/状态机）+ 自绘组件（时间线/Trace 树） | ReactFlow 节点/边/状态着色开箱即用；时间线等轻量组件自绘更可控 | ReactFlow 需 lazy 加载控制首屏 |
| 状态管理 | React Context + hooks，不引入 Redux | 页面间共享状态少（会话/用户），避免过度设计 | 复杂跨页状态（如全局 Agent 运行中任务）用顶层 Context 兜底 |
| 部署形态 | 开发：Vite dev server（`/api` 代理到 8000）；生产：`web/dist` 由 FastAPI `StaticFiles` 托管（同源） | 一条命令起全栈，Demo 演示最顺；开发热更新不受影响 | 生产无独立前端进程（Demo 场景无需） |
| SSE 消费 | `fetch` + ReadableStream 手动解析（非 EventSource） | `POST /chat/stream` 带 body，EventSource 仅支持 GET | 解析代码 ~40 行，封装为 hooks 复用 |

**关键约束说明**：后端不改动（前端适配接口，不新增后端端点）；`X-User-Id` 请求头全局注入（记忆隔离）。

## 三、整体布局与路由

```
┌──────────┬──────────────────────────────────────────────┐
│ 侧边导航  │  顶栏: 健康状态(healthz/readyz) · 用户ID · 文档链接 │
│          ├──────────────────────────────────────────────┤
│ ▸ 对话工作台 │                                              │
│ ▸ Agent 编排 │           主内容区（页面级路由）                │
│ ▸ 研究报告   │                                              │
│ ▸ 知识库    │                                              │
│ ▸ 工具治理  │                                              │
│ ▸ 记忆管理  │                                              │
│ ▸ 可观测    │                                              │
│ ▸ 评测中心  │                                              │
└──────────┴──────────────────────────────────────────────┘
```

| 路由 | 页面 | 核心能力 |
|---|---|---|
| `/chat` | 对话工作台 | SSE 流式对话、引用块、工具调用记录、会话列表、复杂任务 Agent 概览嵌入 |
| `/agent` | Agent 编排（核心页） | 状态机流程图、子任务委派链、事件时间线、Trace 树、原始事件查看 |
| `/reports` | 研究报告 | 报告创建、六阶段流水线可视化、产物预览（引用溯源）、飞书发布 |
| `/knowledge` | 知识库 | 文档上传/列表/删除/重建索引、检索测试 |
| `/tools` | 工具治理 | 治理指标卡、执行域分布、逐工具指标表、Skill 启停（实时刷新可见数） |
| `/memory` | 记忆管理 | 长期记忆列表/删除/手动沉淀 |
| `/observability` | 可观测 | 会话统计卡、Trace 树、Replay 时间轴回放 |
| `/eval` | 评测中心 | 触发评测、指标结果表 |

**顶栏健康状态**：`GET /healthz` + `GET /readyz` 每 10s 轮询，依赖就绪绿灯 / 失败红点（点击显示明细）。

## 四、Agent 编排可视化设计（核心章节）

### 4.1 页面布局（四面板）

```
┌────────────────────────────────────────────────────────────┐
│ 输入区: 示例 query 下拉 + 输入框 + 发送（POST /chat/stream）    │
├──────────────────────────┬─────────────────────────────────┤
│ ① 状态机流程图 (ReactFlow) │ ② 子任务委派链面板                 │
│    START→understand→plan │    主 run + 子 run 树             │
│    →execute→summarize→END│    每子任务: task/status/耗时/     │
│    节点状态实时着色        │    checkpoint_id/工具调用数         │
│    execute 节点内嵌子卡片  │    (GET /agents/runs/{run_id})    │
├──────────────────────────┼─────────────────────────────────┤
│ ③ 事件时间线               │ ④ Trace 树                       │
│    retrieval→tool_start→ │    嵌套 span (agent_decision/    │
│    tool_end→token→done   │    tool_call/retrieval/memory)   │
│    按时间轴排列, 工具带耗时 │    点击展开, 输入输出 JSON 可折叠    │
│    与成败标记              │    (GET /traces/{session_id})    │
└──────────────────────────┴─────────────────────────────────┘
  ⑤ 底部: 原始 SSE 事件 JSON 查看器（开发者模式 toggle）
```

### 4.2 数据流

1. 发送 query → `POST /api/v1/chat/stream`（fetch + ReadableStream 解析 SSE）；
2. 事件驱动更新：
   - `retrieval` → 检索面板（chunks 高亮）
   - `progress`（`stage=multi_agent, delegated, subtasks, run_id`）→ ① 流程图进入 execute 态 + ② 子任务卡片出现
   - `tool_start/tool_end` → ③ 时间线追加 + ② 对应子任务工具调用记录
   - `token` → 对话流打字机（节流渲染，≥50ms 合并）
   - `done`（citations/latency_ms）→ ① 状态机收尾 + 引用块
3. 结束后 `GET /agents/runs/{run_id}` 拉全量委派链（补全状态机快照）；`GET /traces/{session_id}` 拉 Trace 树（④ 面板）。

### 4.3 可视化规范

- **状态着色**：idle 灰 / running 蓝（脉冲动画）/ completed 绿 / failed 红 / skipped 虚线灰；
- **子任务卡片**：标题=task 摘要，徽标=status，副行=latency_ms + checkpoint_id（可复制）；失败卡片红边可点击查看 error；
- **时间线**：横向滚动轴，事件类型图标（检索/工具/令牌/完成），工具事件带延迟柱条与 ✓/✗；
- **Trace 树**：`span_type` 颜色区分（agent_decision 紫 / tool_call 蓝 / retrieval 绿 / memory 橙），展开显示 input/output 截断 JSON + 耗时；
- **开发者模式**：底部原始事件流按时间追加，可复制整段。

### 4.4 报告流水线可视化（/reports 页内嵌）

- 创建后步骤条：`planning → research → synthesis → writing → review → done/failed`，当前步骤脉冲高亮，每步显示 detail 文案（轮询 `GET /reports/{id}`，2s 间隔；预留 SSE 升级点）；
- 完成后产物区：章节正文中 `[n]` 引用渲染为可点击角标 → 点击定位右侧证据包对应条目（来源/文档/分数）；
- 参考文献表 + 审查结论（通过徽标 / 问题清单红色列表）；
- **发布按钮** → `POST /reports/{id}/publish` → 成功展示飞书链接（新窗口打开），降级展示黄色提示条（message 原样呈现）。

## 五、页面功能清单（对应后端 API）

| 页面 | 按钮/操作 | 对应 API |
|---|---|---|
| 对话工作台 | 发送/清空、示例 query、查看引用、查看工具记录 | POST /chat、POST /chat/stream、GET /chat/sessions、GET /chat/sessions/{id}/messages |
| Agent 编排 | 发送、查看委派链、查看 Trace、开发者模式 | 同上 + GET /agents/runs/{id}、GET /traces/{sid} |
| 研究报告 | 创建报告、轮询进度、预览产物、发布飞书 | POST /reports、GET /reports/{id}、GET /reports/{id}/result、POST /reports/{id}/publish |
| 知识库 | 上传（拖拽）、删除、重建索引、检索测试 | POST /documents/upload、GET /documents、DELETE /documents/{id}、POST /documents/{id}/reindex、POST /knowledge/search |
| 工具治理 | Skill 启停、指标刷新 | GET /skills、PUT /skills/{name}/toggle、GET /tools/stats |
| 记忆管理 | 删除记忆、手动沉淀 | GET /memory/{uid}、DELETE /memory/{uid}/{id}、POST /memory/{uid}/sediment |
| 可观测 | 选会话、展开 Trace、Replay 回放 | GET /traces/stats、GET /traces/{sid}、POST /traces/replay |
| 评测中心 | 触发评测、查看结果 | POST /eval/run、GET /eval/runs/{id} |
| 全局 | 健康状态轮询 | GET /healthz、GET /readyz |

## 六、前端目录结构（web/）

```
web/
├── index.html
├── package.json / tsconfig.json / vite.config.ts / tailwind.config.ts
└── src/
    ├── main.tsx / App.tsx                  # 入口 + 路由
    ├── api/
    │   ├── client.ts                       # fetch 封装(统一 X-User-Id/错误解析)
    │   ├── sse.ts                          # fetch+ReadableStream SSE 解析器
    │   └── endpoints.ts                    # 26 个 API 调用函数(对齐后端 schema)
    ├── types/
    │   └── api.ts                          # TS 类型(对齐后端响应模型)
    ├── stores/
    │   ├── SessionContext.tsx              # 用户/会话/全局任务状态
    │   └── AgentRunContext.tsx             # Agent 运行中状态机快照
    ├── hooks/
    │   ├── useChatStream.ts                # SSE 对话流(事件分发)
    │   ├── usePolling.ts                   # 报告/健康状态轮询
    │   └── useAgentRun.ts                  # 委派链/Trace 拉取
    ├── components/
    │   ├── layout/ (Sidebar.tsx Topbar.tsx)
    │   ├── chat/ (MessageBubble.tsx CitationCard.tsx ToolCallChip.tsx)
    │   ├── agent/ (AgentFlowChart.tsx SubtaskPanel.tsx EventTimeline.tsx TraceTree.tsx RawEventViewer.tsx)
    │   ├── report/ (PipelineSteps.tsx ReportPreview.tsx EvidencePanel.tsx PublishButton.tsx)
    │   ├── knowledge/ (UploadZone.tsx DocTable.tsx SearchTester.tsx)
    │   ├── tools/ (StatsCards.tsx DomainBreakdown.tsx ToolMetricsTable.tsx SkillSwitches.tsx)
    │   └── common/ (StatusBadge.tsx JsonViewer.tsx Loading.tsx)
    └── pages/
        ├── ChatPage.tsx AgentPage.tsx ReportsPage.tsx KnowledgePage.tsx
        ├── ToolsPage.tsx MemoryPage.tsx ObservabilityPage.tsx EvalPage.tsx
```

## 七、关键实现要点

1. **SSE 解析**（`api/sse.ts`）：`fetch` 拿到 `ReadableStream` 后按 `event:` / `data:` 行解析，封装为 async generator；组件层 `useChatStream` 消费并分发到各面板；心跳行（`:` 开头）跳过；
2. **流式渲染节流**：token 事件 ≥50ms 合并一次 DOM 更新（打字机效果），避免长回复卡顿；
3. **ReactFlow lazy 加载**：仅 Agent 页按需 `React.lazy` 引入，首屏体积可控；
4. **状态机快照补全**：SSE 只给 `progress` 摘要，结束时拉 `GET /agents/runs/{run_id}` 补全子任务明细（状态机确定性来源）；
5. **类型对齐**：`types/api.ts` 逐一映射后端响应（ChatResponse / ToolGovernanceStats / ReportOut / TraceSpan 树），接口变更时编译期暴露；
6. **预置演示数据**：每个页面提供 1-3 个示例输入（如"对比产品 A/B/C 的价格与参数并汇总"触发委派，"基于知识库总结报销与差旅制度"触发报告），演示即点即用。

## 八、里程碑与验收标准

### M1 脚手架与对话工作台（0.5-1 天）
Vite+React+TS+Tailwind 脚手架、布局、SSE 解析器、对话流式渲染 + 引用块 + 工具记录。
**验收**：`npm run dev` 起前端，对话可流式输出，引用与工具记录可见；`/api` 代理通。

### M2 Agent 可视化 + 知识库（1-2 天）
AgentFlowChart / SubtaskPanel / EventTimeline / TraceTree + 知识库页（上传/列表/检索测试）。
**验收**：复杂任务触发委派时，状态机实时流转、子任务卡片并行更新、时间线完整；知识库上传→索引状态→检索测试全链路可操作。

### M3 工具治理 + 记忆 + 可观测 + 评测（1-2 天）
治理指标卡/域分布/Skill 启停（切换后可见数与 Schema Token 实时刷新）、记忆列表/删除/沉淀、Trace 树 + Replay 回放、评测触发与结果。
**验收**：`/tools/stats` 数据可视化正确；Skill 启停联动指标变化；Replay 可回放历史会话事件。

### M4 报告流水线 + 发布 + 后端托管（1-2 天）
PipelineSteps 六阶段可视化、报告产物预览（引用角标↔证据包联动）、飞书发布、`npm run build` 产物由 FastAPI 托管。
**验收**：报告页全流程（创建→六阶段→预览→发布飞书）可演示；`uvicorn knowflow.main:app` 单端口访问前端页面；门禁（ruff/mypy/pytest）不回归。

### 总验收（功能按钮齐全 + Agent 可视化）
- [ ] 26 个 API 路径均有对应 UI 入口，无死按钮；
- [ ] Agent 编排页四面板联动：SSE 实时驱动状态机/子任务/时间线，结束补全委派链与 Trace 树；
- [ ] 报告页六阶段进度 + 引用溯源联动 + 飞书发布（含降级提示）可演示；
- [ ] 知识库/工具治理/记忆/可观测/评测全部可操作；
- [ ] 构建产物后端托管，`make up` 后单端口访问；
- [ ] 预置示例输入即点即用。

## 九、风险与注意事项

| 风险 | 应对 |
|---|---|
| SSE 为 POST（EventSource 不支持） | fetch + ReadableStream 手动解析（`api/sse.ts`），不修改后端 |
| 开发跨域 | Vite `server.proxy` 代理 `/api` → `localhost:8000`；生产同源无跨域 |
| token 流渲染卡顿 | ≥50ms 合并渲染 + 消息气泡懒挂载 |
| ReactFlow 体积 | 页面级 lazy 加载，首屏不引入 |
| 后端接口演进 | 类型集中 `types/api.ts`，编译期对齐；文档同步 `api_reference.md` |
| 报告进度无 SSE | 2s 轮询 `GET /reports/{id}`（预留 SSE 升级点，后端后续可加） |
