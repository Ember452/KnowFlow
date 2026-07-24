"""MCP 工具适配器 - 把远程 MCP 工具适配为本地 BaseTool.

继承 BaseTool 后自动纳入执行域体系: 注册进 ToolRegistry 即享受
执行域隔离(VisibilityCalculator) / Skill 激活可见 / 指标统计 / 调用记录.
"""

import time
from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.core.logging import get_logger
from knowflow.tools.base import BaseTool, ToolResult
from knowflow.tools.mcp.gateway import McpGateway, McpToolInfo

logger = get_logger(__name__)


class McpToolAdapter(BaseTool):
    """把单个 MCP 远程工具包装成本地 BaseTool 实例.

    Args:
        server_id: MCP Server 逻辑名(工具名前缀 mcp_{server_id}_*, 避免
            多 server 同名工具冲突且可追溯来源).
        info: 远程工具清单条目(name/description/input_schema).
        gateway: 负责转发调用的网关.
        domain: 执行域(默认 SKILL_ONLY: 需所属 Skill 激活才可见).
    """

    def __init__(
        self,
        server_id: str,
        info: McpToolInfo,
        gateway: McpGateway,
        domain: ExecutionDomain = ExecutionDomain.SKILL_ONLY,
    ) -> None:
        self.name = f"mcp_{server_id}_{info.name}"
        self.description = f"[MCP:{server_id}] {info.description}"
        self.domain = domain
        self._info = info
        self._gateway = gateway

    def input_schema(self) -> dict[str, Any]:
        """返回远程工具的输入 JSON Schema."""
        return self._info.input_schema or {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> ToolResult:
        """经网关转发调用远程工具; 失败返回失败 ToolResult(不抛出)."""
        start = time.perf_counter()
        try:
            output = await self._gateway.call_tool(self._info.name, kwargs)
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.warning("mcp.tool_call_failed", tool=self.name, error=str(exc))
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )
