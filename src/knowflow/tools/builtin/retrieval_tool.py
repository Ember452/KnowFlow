"""知识检索工具 - 调 GraphRAGRetriever 检索知识库.

direct 域, 主 Agent 始终可见. execute(query, top_k) 调 retriever.retrieve,
返回 chunk 列表(content 截断防膨胀). retriever 在构造时注入(单例或 fake).
"""

import time
from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.base import BaseTool, ToolResult


class RetrievalTool(BaseTool):
    """知识检索: 调 GraphRAG 检索器返回相关片段. direct 域."""

    name = "retrieval_tool"
    description = "在企业知识库中检索与查询相关的文档片段. 输入 query, 可选 top_k."
    domain = ExecutionDomain.DIRECT

    def __init__(self, retriever: Any) -> None:
        self._retriever = retriever

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询文本"},
                "top_k": {"type": "integer", "description": "返回条数, 默认 5", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        query = str(kwargs.get("query", ""))
        top_k = int(kwargs.get("top_k", 5))
        try:
            result = await self._retriever.retrieve(query, top_k=top_k)
            chunks = [
                {
                    "chunk_id": getattr(c, "chunk_id", None),
                    "content": getattr(c, "content", "")[:500],
                    "score": getattr(c, "score", 0.0),
                    "source": getattr(c, "source", ""),
                }
                for c in result.chunks
            ]
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output={"query": query, "chunks": chunks, "count": len(chunks)},
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )
