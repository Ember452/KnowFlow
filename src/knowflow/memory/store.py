"""长期记忆存储 - PostgreSQL 持久化 + embedding 写入.

embedding 以 JSON 序列化存入 LargeBinary 字段(P2 的 VectorField 约定).
P7 阶段候选量小(单用户数十条), 召回在 Python 内做余弦相似度,
PG 无 pgvector 是本地资源受限的取舍(与 Milvus 风险应对一致).
"""

import asyncio
import json
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.logging import get_logger
from knowflow.models.memory import LongTermMemory

logger = get_logger(__name__)


def _serialize(vector: list[float]) -> bytes:
    """向量序列化(bytes, 存 LargeBinary 字段)."""
    return json.dumps(vector).encode("utf-8")


def deserialize_embedding(raw: bytes | None) -> list[float] | None:
    """反序列化向量; 无值/损坏/类型不符返回 None."""
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, list):
            return None
        return [float(x) for x in data]
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


class LongTermStore:
    """长期记忆存储层. session 为请求级 AsyncSession, embedding_client 可选."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_client: Any | None = None,
    ) -> None:
        self._session = session
        self._embedding = embedding_client

    async def save(
        self,
        *,
        user_id: str,
        session_id: int,
        content: str,
        importance: float,
        summary: str | None = None,
    ) -> int:
        """写入一条长期记忆(含 embedding). 返回记忆 id."""
        embedding: bytes | None = None
        if self._embedding is not None:
            try:
                vector = await asyncio.to_thread(self._embedding.embed_one, content)
                if vector:
                    embedding = _serialize(vector)
            except Exception as exc:
                logger.warning("memory.embedding_failed", error=str(exc))
        memory = LongTermMemory(
            user_id=user_id,
            session_id=session_id,
            content=content,
            summary=summary,
            importance=importance,
            embedding=embedding,
        )
        self._session.add(memory)
        await self._session.flush()
        return int(memory.id)

    async def list_by_user(self, user_id: str) -> list[LongTermMemory]:
        """按用户列出全部长期记忆(创建时间升序)."""
        result = await self._session.execute(
            select(LongTermMemory)
            .where(LongTermMemory.user_id == user_id)
            .order_by(LongTermMemory.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete(self, memory_id: int) -> bool:
        """删除记忆; 不存在返回 False."""
        memory = await self._session.get(LongTermMemory, memory_id)
        if memory is None:
            return False
        await self._session.delete(memory)
        return True

    async def update_content(self, memory_id: int, content: str, importance: float) -> bool:
        """覆盖更新记忆内容与重要性(去重合并用); 不存在返回 False."""
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(LongTermMemory)
                .where(LongTermMemory.id == memory_id)
                .values(content=content, importance=importance)
            ),
        )
        return (result.rowcount or 0) > 0

    async def touch_recall(self, memory_ids: list[int]) -> None:
        """批量更新 last_recall(召回后标记, 参与时间衰减)."""
        if not memory_ids:
            return
        await self._session.execute(
            update(LongTermMemory)
            .where(LongTermMemory.id.in_(memory_ids))
            .values(last_recall=datetime.now())
        )
