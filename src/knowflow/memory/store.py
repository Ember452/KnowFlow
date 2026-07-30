"""长期记忆存储 - PostgreSQL 持久化 + embedding 写入.

embedding 以 JSON 序列化存入 LargeBinary 字段(P2 的 VectorField 约定),
embedding_vec 为 pgvector VECTOR 列: 去重写入时在数据库做向量近似 top-N
检索, 只回传少量候选再做精确校验, 避免全量拉取用户记忆逐条算相似度.
SQL 路径仅在 PG + pgvector 扩展 + 该用户数据全部向量化时启用, 否则降级
Python 全量扫描(行为与旧版一致).
"""

import asyncio
import json
from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.logging import get_logger
from knowflow.models.memory import LongTermMemory

logger = get_logger(__name__)

# pgvector 能力探测结果缓存(按 engine 隔离, 生产单 engine 一次探测)
_pgvector_ready_cache: dict[int, bool] = {}


async def _pgvector_ready(session: AsyncSession) -> bool:
    """PG + vector 扩展 + embedding_vec 列齐备才返回 True(结果按 engine 缓存)."""
    bind = session.get_bind()
    engine_id = id(bind)
    cached = _pgvector_ready_cache.get(engine_id)
    if cached is not None:
        return cached
    ready = False
    if bind.dialect.name == "postgresql":
        try:
            sql = text(
                "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')"
                " AND EXISTS (SELECT 1 FROM information_schema.columns"
                " WHERE table_schema = current_schema()"
                " AND table_name = 'long_term_memories' AND column_name = 'embedding_vec')"
            )
            ready = bool(await session.scalar(sql))
        except Exception as exc:
            logger.warning("memory.pgvector_probe_failed", error=str(exc))
    _pgvector_ready_cache[engine_id] = ready
    return ready


def _serialize(vector: list[float]) -> bytes:
    """向量序列化(bytes, 存 LargeBinary 字段)."""
    return json.dumps(vector).encode("utf-8")


def _build_dedup_query(user_id: str, vec_str: str, top_n: int) -> Select[Any]:
    """构造去重 top-N 检索语句: 余弦距离升序(= 相似度降序), 距离计算下推数据库.

    向量以文本 "[x,y,...]" 绑定并 CAST 为 vector, 避免依赖驱动的向量类型编解码.
    """
    return (
        select(LongTermMemory)
        .where(
            LongTermMemory.user_id == user_id,
            LongTermMemory.embedding_vec.is_not(None),
        )
        .order_by(text("embedding_vec <=> CAST(:query_vec AS vector)"))
        .params(query_vec=vec_str)
        .limit(top_n)
    )


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

    @property
    def session(self) -> AsyncSession:
        """底层 AsyncSession(蒸馏/冲突等跨模型操作复用)."""
        return self._session

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
        embedding_vec: list[float] | None = None
        if self._embedding is not None:
            try:
                vector = await asyncio.to_thread(self._embedding.embed_one, content)
                if vector:
                    embedding = _serialize(vector)
                    if await _pgvector_ready(self._session):
                        embedding_vec = vector
            except Exception as exc:
                logger.warning("memory.embedding_failed", error=str(exc))
        memory = LongTermMemory(
            user_id=user_id,
            session_id=session_id,
            content=content,
            summary=summary,
            importance=importance,
            embedding=embedding,
            embedding_vec=embedding_vec,
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

    async def find_duplicate_candidates(
        self, user_id: str, query_vec: list[float], top_n: int
    ) -> list[LongTermMemory] | None:
        """数据库向量 top-N 候选(去重用).

        余弦相似度下推数据库(embedding_vec <=> :query_vec 升序即相似度降序),
        只回传少量候选, 由调用方做精确余弦二次校验.

        Returns:
            候选记忆列表; 能力不可用(非 PG / 无扩展 / 列缺失)或该用户存在
            未向量化的存量数据时返回 None, 调用方应降级 Python 全量扫描.
        """
        if not await _pgvector_ready(self._session):
            return None
        try:
            legacy = (
                await self._session.scalar(
                    select(func.count())
                    .select_from(LongTermMemory)
                    .where(
                        LongTermMemory.user_id == user_id,
                        LongTermMemory.embedding_vec.is_(None),
                    )
                )
                or 0
            )
            if legacy:
                return None
            vec_str = "[" + ",".join(str(x) for x in query_vec) + "]"
            result = await self._session.execute(_build_dedup_query(user_id, vec_str, top_n))
            return list(result.scalars().all())
        except Exception as exc:
            logger.warning("memory.dedup_vector_query_failed", error=str(exc))
            return None

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
