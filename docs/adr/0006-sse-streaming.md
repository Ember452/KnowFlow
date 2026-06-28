# ADR 0006: 流式用 SSE 不用 WebSocket

- 状态: Accepted
- 日期: 2026-06-05
- 关联: 设计文档 D5 / P5 对话链路

## Context

对话链路需要把 LLM 的 token 流式输出给前端。可选方案：SSE（Server-Sent Events）或 WebSocket。
知识问答是**单向流式输出**（服务端 → 客户端），没有双向实时交互需求（工具调用是服务端内部行为，非用户实时操作）。

WebSocket 需要独立协议处理（升级握手、心跳、帧编码、断线重连逻辑），复杂度明显高于 SSE；
SSE 基于普通 HTTP，FastAPI 原生支持，自动重连由浏览器 EventSource 内置。

## Decision

**流式用 SSE 不用 WebSocket**：`sse-starlette` 提供事件流封装，事件序列 `retrieval → tool_start/tool_end → token* → done`，
15s 心跳保活，客户端断开检测（`request.is_disconnected`）主动取消生成器。
双向需求（未来若需用户实时打断/操作）再引入 WebSocket，当前场景不需要。

## Consequences

正面:
- 轻量: 普通 HTTP 传输, 无协议握手/帧编码, FastAPI 原生支持.
- 兼容性好: 任意 HTTP 客户端可消费, 浏览器 EventSource 自动重连.
- 事件模型简单: 文本事件流即可表达 retrieval/token/done 等阶段.

负面:
- 仅支持服务端→客户端单向推送, 客户端上行仍需普通请求(当前场景足够).
- 无二进制帧支持(LLM 文本输出不受影响).
- 长连接占用: 由心跳与超时控制, 与 WebSocket 相比连接资源开销略高.
