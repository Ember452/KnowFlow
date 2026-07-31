# ADR 0009: 飞书接入走自建 MCP server

- 状态: Accepted
- 日期: 2026-08-10
- 关联: 设计文档 5.5 / 5.7 D9 / P13 飞书 MCP 接入与报告发布

## Context

V2 要求报告一键写入用户飞书云文档。接入方式有两种：

方案 A：业务代码直接调飞书开放平台 SDK（lark）。实现最快，但绕开既有工具治理体系
（执行域隔离/权限校验/trace），无法证明"MCP 生态可扩展"这一项目核心能力，且发布动作
游离于可观测体系之外。

方案 B：自建 feishu MCP server（stdio 协议），暴露 create_doc/append_to_doc/update_doc，
经 settings.mcp_servers 配置声明接入，走既有注册链路（register_mcp_server → McpToolAdapter
→ 工具注册表 → 域隔离 → 权限校验 → trace）。

## Decision

**飞书能力走 MCP server 接入，官方 server 优先、自建兜底**：优先接入飞书开放平台官方
lark-openapi-mcp（stdio 协议，npx 启动），其工具经 `register_mcp_server` 的 `allow_tools`
白名单过滤后注册，工具域为 skill_only（仅报告发布阶段激活注入）；无 Node 环境或官方工具名
不确定时，回退到自建 `tools/mcp/servers/feishu/server.py`（lark SDK 封装，工具名固定
create_doc/append_to_doc/update_doc）。平台代码零侵入，飞书能力与既有工具同权治理。

## Consequences

正面:
- MCP 生态真实接入闭环: "注册→治理→隔离→调用→trace"全链路可演示, 补齐项目最大扩展性缺口.
- 零侵入: 不改工具治理代码, 只加配置与 server 实现.
- 治理一致: 发布动作受域隔离/权限校验/trace 约束, 与内置工具同等可观测.
- 官方优先: 接入第三方现成 MCP server 是对"MCP 生态可扩展"的更强实证; allow_tools 白名单控制工具膨胀.

负面:
- 多一层进程通信(stdio), 发布延迟略增(报告场景可接受).
- 需维护飞书开放平台凭证配置(app_id/app_secret), 凭证仅存环境变量, 不落库.
- 官方 server 依赖 Node/npx 环境, 自建 server 兜底时需维护 lark SDK 依赖(可选, 未配置凭证时注册降级跳过).
