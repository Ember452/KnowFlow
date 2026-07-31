"""MCP 工具网关 - stdio 连接 MCP Server, 拉取工具清单并转发调用.

每次操作建立独立连接(子进程生命周期随连接), 连接/调用失败抛
McpConnectionError, 由上层(注册工厂/适配器)降级: 工具不可用不阻塞对话.
调用超时由 mcp_call_timeout_seconds 控制(默认 30s, 超时抛 McpConnectionError),
防止远端 server 挂死拖死调用方.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


class McpConnectionError(RuntimeError):
    """MCP 连接/调用失败."""


@dataclass(frozen=True)
class McpToolInfo:
    """MCP 远程工具清单条目(list_tools 结果)."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] | None = None


class McpGateway:
    """stdio 模式 MCP 网关: list_tools 拉清单, call_tool 转发调用."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> None:
        """初始化.

        Args:
            command: server 启动命令(可执行文件路径).
            args: 启动参数(如 ["-m", "knowflow.tools.mcp.servers.demo"]).
            env: 附加环境变量(叠加在继承环境之上).
            timeout: 单次工具调用超时秒数; None 取 settings.mcp_call_timeout_seconds.
        """
        self._params = StdioServerParameters(command=command, args=args or [], env=env)
        settings: Settings = get_settings()
        self._timeout = timeout if timeout is not None else float(settings.mcp_call_timeout_seconds)

    async def list_tools(self) -> list[McpToolInfo]:
        """建立连接并拉取工具清单."""
        async with self._connect() as session:
            tools = await session.list_tools()
            return [
                McpToolInfo(
                    name=t.name,
                    description=t.description or "",
                    input_schema=dict(t.input_schema or {}),
                )
                for t in tools.tools
            ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """调用远程工具, 返回文本内容拼接结果.

        Raises:
            McpConnectionError: 连接失败/远程工具执行失败(is_error)/调用超时.
        """
        async with self._connect() as session:
            coro = session.call_tool(name, arguments or {})
            if self._timeout and self._timeout > 0:
                try:
                    result = await asyncio.wait_for(coro, self._timeout)
                except TimeoutError as exc:
                    raise McpConnectionError(f"MCP 工具调用超时({self._timeout}s): {name}") from exc
            else:
                result = await coro
        if getattr(result, "is_error", False):
            text = self._extract_text(result)
            raise McpConnectionError(f"MCP 工具执行失败({name}): {text or '未知错误'}")
        return self._extract_text(result)

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[ClientSession]:
        """组合式异步上下文: stdio 连接 + 会话初始化, 退出时逆序清理.

        连接/初始化失败抛 McpConnectionError; 已建立的资源在异常路径也确保关闭.
        """
        cm = stdio_client(self._params)
        try:
            read, write = await cm.__aenter__()
            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()
        except Exception as exc:
            with suppress(Exception):
                await cm.__aexit__(None, None, None)
            raise McpConnectionError(f"MCP 连接失败({self._params.command}): {exc}") from exc
        try:
            yield session
        finally:
            await session.__aexit__(None, None, None)
            await cm.__aexit__(None, None, None)

    @staticmethod
    def _extract_text(result: Any) -> str:
        """从 call_tool 结果提取文本内容(兼容 TextContent 等类型)."""
        parts: list[str] = []
        for content in getattr(result, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                parts.append(str(text))
        return "\n".join(parts)
