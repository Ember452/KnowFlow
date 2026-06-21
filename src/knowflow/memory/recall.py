"""长期记忆召回 - 语义相似度 + 时间衰减, last_recall 参与排序.

召回分数 = 0.7 * 余弦相似度 + 0.2 * 重要性归一 + 0.1 * 新鲜度.
新鲜度 = 1 / (1 + 距上次召回天数/7), last_recall 越近权重越高
(刚召回过的记忆再次命中的概率更高, 体现"用进废退").
召回后批量 touch last_recall.
"""

import asyncio
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.memory.store import LongTermStore, deserialize_embedding

# 召回分数权重
_W_SIM = 0.7
_W_IMPORTANCE = 0.2
_W_RECENCY = 0.1
_DECAY_DAYS = 7.0  # 时间衰减半程(天)


@dataclass(frozen=True)
class MemoryHit:
    """单条召回结果."""

    memory_id: int
    content: str
    importance: float
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """余弦相似度; 空向量或维度不一致返回 0."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _to_utc(dt: datetime) -> datetime:
    """naive 时间视为 UTC(SQLite 不保留时区), aware 时间归一 UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class LongTermRecaller:
    """长期记忆召回器: 相关度 + 时间衰减排序."""

    def __init__(
        self,
        store: LongTermStore,
        embedding_client: Any | None = None,
        settings: Settings | None = None,
        top_k: int | None = None,
    ) -> None:
        self._store = store
        self._embedding = embedding_client
        self._settings = settings or get_settings()
        self._top_k = top_k if top_k is not None else self._settings.memory_recall_top_k

    async def recall(
        self,
        query: str,
        user_id: str,
        top_k: int | None = None,
    ) -> list[MemoryHit]:
        """按查询召回用户长期记忆, 按分数降序取 top_k 并 touch last_recall."""
        memories = await self._store.list_by_user(user_id)
        if not memories:
            return []
        limit = top_k if top_k is not None else self._top_k
        query_vec: list[float] = []
        if self._embedding is not None:
            query_vec = await asyncio.to_thread(self._embedding.embed_one, query)

        now = datetime.now(UTC)
        scored: list[MemoryHit] = []
        for m in memories:
            m_vec = deserialize_embedding(m.embedding) or []
            sim = cosine_similarity(query_vec, m_vec) if query_vec else 0.0
            importance_norm = max(0.0, min(1.0, (m.importance or 0.0) / 10.0))
            last = m.last_recall or m.created_at
            if last is not None:
                days = (now - _to_utc(last)).total_seconds() / 86400.0
            else:
                days = _DECAY_DAYS
            recency = 1.0 / (1.0 + max(0.0, days) / _DECAY_DAYS)
            score = _W_SIM * sim + _W_IMPORTANCE * importance_norm + _W_RECENCY * recency
            scored.append(
                MemoryHit(
                    memory_id=int(m.id),
                    content=m.content,
                    importance=m.importance or 0.0,
                    score=round(score, 4),
                )
            )

        scored.sort(key=lambda h: h.score, reverse=True)
        top = scored[:limit]
        await self._store.touch_recall([h.memory_id for h in top])
        return top
