"""长期记忆门面 - store + recall 统一入口, 供 MemoryManager 与 API 使用."""

import asyncio
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.memory.recall import LongTermRecaller, MemoryHit, cosine_similarity
from knowflow.memory.store import LongTermStore, deserialize_embedding
from knowflow.models.memory import LongTermMemory, MemorySummary

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
        """查找与 content 高度相似的已有记忆(语义优先, 无 embedding 时文本兜底).

        语义路径优先走数据库向量 top-N(pgvector, 余弦相似度下推 SQL),
        只回传少量候选再做精确余弦二次校验; 数据库路径不可用(非 PG /
        无扩展 / 用户存在未向量化存量数据)时降级 Python 全量扫描,
        判定逻辑与旧版完全一致.
        """
        threshold = self._settings.memory_dedup_threshold
        vec = await self._embed_for_dedup(content)
        if vec:
            candidates = await self._store.find_duplicate_candidates(
                user_id, vec, self._settings.memory_dedup_candidate_count
            )
            if candidates is not None:
                best, best_sim = self._best_by_cosine(candidates, vec)
                if best is not None and best_sim >= threshold:
                    return best
                return None
            # 数据库路径不可用: 降级 Python 全量扫描(旧逻辑)
            memories = await self._store.list_by_user(user_id)
            if memories:
                best, best_sim = self._best_by_cosine(memories, vec)
                if best is not None:
                    return best if best_sim >= threshold else None
                # 全部无向量: 文本相似度兜底
                return await self._find_duplicate_text(user_id, content, threshold)
            return None
        # 无 embedding 或 embedding 失败: 文本相似度兜底
        return await self._find_duplicate_text(user_id, content, threshold)

    async def _embed_for_dedup(self, content: str) -> list[float]:
        """去重用 embedding; 无客户端或失败返回空列表(走文本兜底)."""
        if self._embedding is None:
            return []
        try:
            return await asyncio.to_thread(self._embedding.embed_one, content)
        except Exception as exc:
            logger.warning("memory.dedup_embedding_failed", error=str(exc))
            return []

    @staticmethod
    def _best_by_cosine(
        memories: list[LongTermMemory], vec: list[float]
    ) -> tuple[LongTermMemory | None, float]:
        """候选集内取余弦相似度最高的一条(全部无向量时返回 (None, 0.0))."""
        best: LongTermMemory | None = None
        best_sim = 0.0
        for m in memories:
            sim = cosine_similarity(vec, deserialize_embedding(m.embedding) or [])
            if sim > best_sim:
                best_sim, best = sim, m
        return best, best_sim

    async def _find_duplicate_text(
        self, user_id: str, content: str, threshold: float
    ) -> LongTermMemory | None:
        """文本相似度兜底: 无 embedding / 全部无向量(近似表述也算重复)."""
        memories = await self._store.list_by_user(user_id)
        best: LongTermMemory | None = None
        best_sim = 0.0
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

    # ── 记忆蒸馏(核心记忆): 会话摘要沉淀与召回注入 ──

    async def save_summary(self, user_id: str, session_id: int, summary: str) -> int:
        """沉淀会话级记忆摘要(蒸馏产物), 返回摘要 id.

        同一会话重复沉淀时覆盖旧摘要, 避免摘要膨胀(保留最新浓缩结果).
        """
        if not summary:
            return 0
        existing = await self._store.session.scalar(
            select(MemorySummary).where(
                MemorySummary.user_id == user_id,
                MemorySummary.session_id == session_id,
            )
        )
        if existing is not None:
            existing.summary = summary
            await self._store.session.flush()
            return int(existing.id)
        entry = MemorySummary(user_id=user_id, session_id=session_id, summary=summary)
        self._store.session.add(entry)
        await self._store.session.flush()
        return int(entry.id)

    async def latest_summary(self, user_id: str) -> str | None:
        """取用户最近一次会话摘要(核心记忆注入用), 无摘要返回 None."""
        entry = await self._store.session.scalar(
            select(MemorySummary)
            .where(MemorySummary.user_id == user_id)
            .order_by(MemorySummary.updated_at.desc())
            .limit(1)
        )
        return entry.summary if entry is not None else None
