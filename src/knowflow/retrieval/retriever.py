"""GraphRAG 检索统一入口 - 编排 hybrid -> expand -> rerank -> cache 完整链路.

流程: cache.get -> miss 时 hybrid_search.search(top_k*2) -> expander.expand ->
reranker.rerank(top_k) -> cache.set -> 返回 RetrievalResult.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.db.repositories.document_repo import ChunkRepo
from knowflow.retrieval.cache import RetrievalCache
from knowflow.retrieval.expander import Expander
from knowflow.retrieval.hybrid_search import ChunkScore, HybridSearch
from knowflow.retrieval.reranker import Reranker


@dataclass(frozen=True)
class ChunkWithScore:
    """检索返回的单条 chunk(含内容与分数)."""

    chunk_id: int
    content: str
    score: float
    source: str


@dataclass(frozen=True)
class RetrievalResult:
    """检索结果."""

    chunks: list[ChunkWithScore] = field(default_factory=list)
    query: str = ""
    latency_ms: float = 0.0
    cache_hit: bool = False


class GraphRAGRetriever:
    """GraphRAG 检索器. 编排完整检索链路."""

    def __init__(
        self,
        session_factory: Any,
        hybrid_search: HybridSearch,
        expander: Expander,
        reranker: Reranker,
        cache: RetrievalCache,
    ) -> None:
        """初始化.

        Args:
            session_factory: 异步 session factory(可调用, 返回 AsyncSession).
            hybrid_search: 混合检索器.
            expander: 一跳扩展器.
            reranker: 精排器.
            cache: 检索缓存.
        """
        self._session_factory = session_factory
        self._hybrid_search = hybrid_search
        self._expander = expander
        self._reranker = reranker
        self._cache = cache

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        with_expand: bool = True,
        with_rerank: bool = True,
    ) -> RetrievalResult:
        """执行完整检索链路.

        Args:
            query: 查询文本.
            top_k: 返回条数, None 时取 settings.retrieval_top_k.
            with_expand: 是否启用一跳扩展.
            with_rerank: 是否启用 reranker 精排.

        Returns:
            RetrievalResult, 含 chunks/query/latency_ms/cache_hit.
        """
        start = time.perf_counter()

        if top_k is None:
            from knowflow.core.config import get_settings

            top_k = get_settings().retrieval_top_k

        # 1. 缓存查询
        cached = await self._cache.get(query)
        if cached is not None:
            # 缓存命中: 直接返回(需要从 DB 取 chunk 内容)
            chunks = await self._fetch_chunks(cached)
            latency_ms = (time.perf_counter() - start) * 1000
            return RetrievalResult(
                chunks=chunks,
                query=query,
                latency_ms=latency_ms,
                cache_hit=True,
            )

        # 2. Hybrid 召回(取 top_k*2 候选, 给 expand/rerank 留余量)
        candidate_k = top_k * 2
        hits = self._hybrid_search.search(query, candidate_k)

        # 3. 一跳扩展
        if with_expand and hits:
            # expander 需要 AsyncSession, 从 factory 取
            session: AsyncSession = await self._get_session()
            try:
                hits = await self._expander.expand(hits)
            finally:
                await session.close()

        # 4. Reranker 精排
        if with_rerank and hits:
            session = await self._get_session()
            try:
                chunks_orm = await self._fetch_chunks_orm([h.chunk_id for h in hits], session)
                reranked = self._reranker.rerank(query, chunks_orm, top_k=len(chunks_orm))
                # 用 rerank 结果替换 hits, 保留 top_k
                hits = reranked[:top_k]
            finally:
                await session.close()

        # 截断到 top_k(expand 后可能超过)
        hits = hits[:top_k]

        # 5. 取 chunk 内容
        chunks = await self._fetch_chunks(hits)

        # 6. 写缓存
        await self._cache.set(query, hits)

        latency_ms = (time.perf_counter() - start) * 1000
        return RetrievalResult(
            chunks=chunks,
            query=query,
            latency_ms=latency_ms,
            cache_hit=False,
        )

    async def _get_session(self) -> Any:
        """从 session factory 获取 AsyncSession."""
        # session_factory 可以是 async_sessionmaker 或可调用对象
        factory = self._session_factory
        if callable(factory):
            return factory()
        # 如果直接是 session 实例
        return factory

    async def _fetch_chunks_orm(self, chunk_ids: Sequence[int], session: Any) -> list[Any]:
        """从 DB 取 chunk ORM 列表(保留输入顺序)."""
        if not chunk_ids:
            return []
        repo = ChunkRepo(session)
        return list(await repo.get_many(chunk_ids))

    async def _fetch_chunks(self, hits: Sequence[ChunkScore]) -> list[ChunkWithScore]:
        """从 DB 取 chunk 内容并组装 ChunkWithScore."""
        if not hits:
            return []
        session = await self._get_session()
        try:
            chunks_orm = await self._fetch_chunks_orm([h.chunk_id for h in hits], session)
            # 按 hits 顺序匹配 ORM
            orm_by_id = {c.id: c for c in chunks_orm}
            result: list[ChunkWithScore] = []
            for h in hits:
                orm = orm_by_id.get(h.chunk_id)
                if orm is not None:
                    result.append(
                        ChunkWithScore(
                            chunk_id=h.chunk_id,
                            content=orm.content,
                            score=h.score,
                            source=h.source,
                        )
                    )
            return result
        finally:
            await session.close()
