"""网络搜索工具 - duckduckgo-search 懒加载.

subagent_only 域(专家工具, 仅子 Agent 可见). duckduckgo_search 为可选依赖,
未安装时 execute 返回失败 ToolResult(不阻塞启动). 离线环境/CI 可用 fake 注入.
"""

import time
from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.base import BaseTool, ToolResult


class SearchTool(BaseTool):
    """网络搜索: duckduckgo 查询. subagent_only 域."""

    name = "search_tool"
    description = "网络搜索(duckduckgo). 输入查询文本, 返回前 N 条结果摘要."
    domain = ExecutionDomain.SUBAGENT_ONLY

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询文本"},
                "max_results": {"type": "integer", "description": "返回条数, 默认 5", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        query = str(kwargs.get("query", ""))
        max_results = int(kwargs.get("max_results", 5))
        try:
            results = await self._search(query, max_results)
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output={"query": query, "results": results, "count": len(results)},
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name, success=False, error=str(exc), latency_ms=round(latency_ms, 2)
            )

    async def _search(self, query: str, max_results: int) -> list[dict[str, str]]:
        """懒加载 duckduckgo_search 并执行查询. 未安装时抛错."""
        try:
            from duckduckgo_search import DDGS
        except ImportError as exc:
            raise RuntimeError("网络搜索依赖未安装: pip install duckduckgo-search") from exc

        def _do_sync() -> list[dict[str, str]]:
            out: list[dict[str, str]] = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    out.append(
                        {
                            "title": str(r.get("title", "")),
                            "snippet": str(r.get("body", "")),
                            "url": str(r.get("href", "")),
                        }
                    )
            return out

        import asyncio

        return await asyncio.to_thread(_do_sync)
