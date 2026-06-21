"""长期记忆门面 - store + recall 统一入口, 供 MemoryManager 与 API 使用."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.memory.recall import LongTermRecaller, MemoryHit
from knowflow.memory.store import LongTermStore


class LongTermMemoryManager:
    """长期记忆管理器: 保存/召回/查询/删除."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: Any | None = None,
        store: LongTermStore | None = None,
        recaller: LongTermRecaller | None = None,
    ) -> None:
        self._store = store or LongTermStore(session, embedding_client)
        self._recaller = recaller or LongTermRecaller(self._store, embedding_client)

    async def save(
        self,
        *,
        user_id: str,
        session_id: int,
        content: str,
        importance: float,
        summary: str | None = None,
    ) -> int:
        """写入一条长期记忆, 返回记忆 id."""
        return await self._store.save(
            user_id=user_id,
            session_id=session_id,
            content=content,
            importance=importance,
            summary=summary,
        )

    async def recall(self, query: str, user_id: str, top_k: int | None = None) -> list[MemoryHit]:
        """按查询召回(相关度 + 时间衰减)."""
        return await self._recaller.recall(query, user_id, top_k=top_k)

    async def list_by_user(self, user_id: str) -> list[Any]:
        """列出用户全部长期记忆."""
        return await self._store.list_by_user(user_id)

    async def delete(self, memory_id: int) -> bool:
        """删除一条记忆; 不存在返回 False."""
        return await self._store.delete(memory_id)
