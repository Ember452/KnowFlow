"""长期记忆门面 - store + recall 统一入口, 供 MemoryManager 与 API 使用."""

import asyncio
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.memory.recall import LongTermRecaller, MemoryHit, cosine_similarity
from knowflow.memory.store import LongTermStore, deserialize_embedding
from knowflow.models.memory import LongTermMemory

logger = get_logger(__name__)


class LongTermMemoryManager:
    """长期记忆管理器: 保存(含去重合并)/召回/查询/删除."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: Any | None = None,
        store: LongTermStore | None = None,
        recaller: LongTermRecaller | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._embedding = embedding_client
        self._store = store or LongTermStore(session, embedding_client)
        self._recaller = recaller or LongTermRecaller(self._store, embedding_client)
        self._settings = settings or get_settings()

    async def save(
        self,
        *,
        user_id: str,
        session_id: int,
        content: str,
        importance: float,
        summary: str | None = None,
    ) -> int:
        """写入一条长期记忆, 返回记忆 id.

        与已有记忆高度相似(重复偏好)时覆盖更新旧条目(内容取新表述,
        importance 取较大值), 避免同一偏好反复沉淀造成冗余存储.
        """
        dup = await self._find_duplicate(user_id, content)
        if dup is not None:
            await self._store.update_content(
                int(dup.id), content, max(dup.importance or 0.0, importance)
            )
            return int(dup.id)
        return await self._store.save(
            user_id=user_id,
            session_id=session_id,
            content=content,
            importance=importance,
            summary=summary,
        )

    async def _find_duplicate(self, user_id: str, content: str) -> LongTermMemory | None:
        """查找与 content 高度相似的已有记忆(语义优先, 无 embedding 时文本兜底)."""
        memories = await self._store.list_by_user(user_id)
        if not memories:
            return None
        threshold = self._settings.memory_dedup_threshold
        best: LongTermMemory | None = None
        best_sim = 0.0
        if self._embedding is not None:
            try:
                vec = await asyncio.to_thread(self._embedding.embed_one, content)
            except Exception as exc:
                logger.warning("memory.dedup_embedding_failed", error=str(exc))
                vec = []
            if vec:
                for m in memories:
                    sim = cosine_similarity(vec, deserialize_embedding(m.embedding) or [])
                    if sim > best_sim:
                        best_sim, best = sim, m
        if best is None:
            # 文本相似度兜底: 无 embedding 或全部无向量(近似表述也算重复)
            for m in memories:
                sim = SequenceMatcher(None, content, m.content).ratio()
                if sim > best_sim:
                    best_sim, best = sim, m
        if best is not None and best_sim >= threshold:
            return best
        return None

    async def recall(self, query: str, user_id: str, top_k: int | None = None) -> list[MemoryHit]:
        """按查询召回(相关度 + 时间衰减)."""
        return await self._recaller.recall(query, user_id, top_k=top_k)

    async def list_by_user(self, user_id: str) -> list[Any]:
        """列出用户全部长期记忆."""
        return await self._store.list_by_user(user_id)

    async def delete(self, memory_id: int) -> bool:
        """删除一条记忆; 不存在返回 False."""
        return await self._store.delete(memory_id)
