"""记忆检索工具 - 包装长期记忆召回器, 供 Agent 工具循环使用(direct 域).

召回源: memory/recall.py 的 LongTermRecaller.recall(query, user_id, top_k)
(或任何实现同签名 async recall 的召回器), 输出内容列表(含重要性/分数),
供模型判断是否注入上下文. 未注入召回器时懒加载(每次调用独立 session).
"""

import time
from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.base import BaseTool, ToolResult


class MemoryTool(BaseTool):
    """长期记忆检索: 按查询召回用户跨会话记忆. direct 域."""

    name = "memory_tool"
    description = "长期记忆检索. 输入查询文本, 返回用户历史记忆中最相关的若干条."
    domain = ExecutionDomain.DIRECT

    def __init__(self, recaller: Any | None = None, default_user_id: str = "anonymous") -> None:
        """初始化.

        Args:
            recaller: 实现 async recall(query, user_id, top_k) 的对象;
                None 时懒加载(LongTermMemoryManager, 每次调用独立 session).
            default_user_id: 未显式传 user_id 时的默认用户标识.
        """
        self._recaller = recaller
        self._default_user_id = default_user_id

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索查询文本"},
                "user_id": {"type": "string", "description": "用户标识, 缺省用默认用户"},
                "top_k": {"type": "integer", "description": "返回条数, 缺省取配置默认值"},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行记忆召回; 失败返回失败 ToolResult(不抛出)."""
        start = time.perf_counter()
        query = str(kwargs.get("query", ""))
        user_id = str(kwargs.get("user_id") or self._default_user_id)
        top_k = kwargs.get("top_k")
        try:
            if self._recaller is not None:
                hits = await self._recaller.recall(query, user_id, top_k=top_k)
            else:
                hits = await self._recall_fallback(query, user_id, top_k)
            output = [
                {"content": h.content, "importance": h.importance, "score": h.score} for h in hits
            ]
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
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

    @staticmethod
    async def _recall_fallback(query: str, user_id: str, top_k: int | None) -> list[Any]:
        """懒加载召回路径: 每次调用独立 session(函数内 import 避免循环依赖)."""
        from knowflow.db.base import get_session_factory
        from knowflow.memory.long_term import LongTermMemoryManager
        from knowflow.retrieval.embedding import get_embedding_client

        factory = get_session_factory()
        async with factory() as session:
            manager = LongTermMemoryManager(session, embedding_client=get_embedding_client())
            return await manager.recall(query, user_id, top_k=top_k)
