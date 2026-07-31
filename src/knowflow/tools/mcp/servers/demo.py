"""内置示例 MCP Server(stdio) - 演示 MCP 工具接入与单测/评测用.

提供两个工具: echo(回显) 与 server_time(服务器时间).
以 `python -m knowflow.tools.mcp.servers.demo` 启动为独立进程,
供 McpGateway 经 stdio 协议真实连接, 走通
"注册 → 治理 → 隔离 → 调用 → trace" 全链路.
"""

import asyncio
from datetime import UTC, datetime

from mcp.server.mcpserver import MCPServer

server = MCPServer(name="knowflow-demo", version="0.1.0")


@server.tool()
async def echo(message: str) -> str:
    """回显输入文本(连接/参数透传验证用)."""
    return f"echo:{message}"


@server.tool()
def server_time() -> str:
    """返回服务器当前 UTC 时间(ISO 格式)."""
    return datetime.now(UTC).isoformat()


@server.tool()
async def boom() -> str:
    """故意抛错(错误路径验证用: 工具执行失败经 is_error 透传)."""
    raise ValueError("boom: 模拟工具执行失败")


@server.tool()
async def slow() -> str:
    """故意慢响应(调用超时验证用: gateway 超时后降级)."""
    await asyncio.sleep(30)
    return "slow: 不应被返回"


def main() -> None:
    """stdio 模式启动入口(子进程方式被 McpGateway 拉起)."""
    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
