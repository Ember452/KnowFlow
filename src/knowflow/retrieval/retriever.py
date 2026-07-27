"""混合检索统一入口 - 编排 hybrid -> rerank -> cache 完整链路.

流程: cache.get -> miss 时 hybrid_search.search(top_k*2) ->
reranker.rerank(top_k) -> cache.set -> 返回 RetrievalResult.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from knowflow.core.logging import get_logger
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentRepo
from knowflow.retrieval.cache import RetrievalCache
from knowflow.retrieval.hybrid_search import ChunkScore, HybridSearch
from knowflow.retrieval.reranker import Reranker

logger = get_logger(__name__)


@dataclass(frozen=True)
class ChunkWithScore:
    """检索返回的单条 chunk(含内容、分数与文档出处)."""

    chunk_id: int
    content: str
    score: float
    source: str
    doc_id: int | None = None
    doc_title: str | None = None


@dataclass(frozen=True)
class RetrievalResult:
    """检索结果."""

    chunks: list[ChunkWithScore] = field(default_factory=list)
    query: str = ""
    latency_ms: float = 0.0
    cache_hit: bool = False


class HybridRetriever:
    """混合检索器. 编排 hybrid 召回 + reranker 精排 + 缓存链路."""

    def __init__(
        self,
        session_factory: Any,
        hybrid_search: HybridSearch,
        reranker: Reranker,
        cache: RetrievalCache,
    ) -> None:
        """初始化.

        Args:
            session_factory: 异步 session factory(可调用, 返回 AsyncSession).
            hybrid_search: 混合检索器.
            reranker: 精排器.
            cache: 检索缓存.
        """
        self._session_factory = session_factory
        self._hybrid_search = hybrid_search
        self._reranker = reranker
        self._cache = cache

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        with_rerank: bool = True,
    ) -> RetrievalResult:
        """执行完整检索链路.

        Args:
            query: 查询文本.
            top_k: 返回条数, None 时取 settings.retrieval_top_k.
            with_rerank: 是否启用 reranker 精排.

        Returns:
            RetrievalResult, 含 chunks(带文档出处 doc_id/doc_title)/query/latency_ms/cache_hit.
        """
        # 首先记录开始时间
        start = time.perf_counter()

        if top_k is None:
            from knowflow.core.config import get_settings

            top_k = get_settings().retrieval_top_k

        # 1. 缓存查询
        # 如果缓存中命中,直接返回缓存中的chunk和查询时间
        # key 由 query + 检索参数(top_k/with_rerank) 共同决定,
        # 避免参数不一致的请求命中彼此缓存返回错误结果
        cached = await self._cache.get(query, top_k=top_k, with_rerank=with_rerank)
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

        # 在PostgreSQL中存储分块正文和对应的id等
        # 在Milvus中存储向量, id docxid
        # 在Redis中存储的是chunkID, Score, Source

        # 2. Hybrid 召回(取 top_k*2 候选, 给 rerank 留余量)
        # 进行向量检索和BM25双路召回2topK,得到RRF融合后的结果topK
        # RRF 的逻辑是1/(k+rank), 其中k是RRF参数, rank是召回结果的排名,因为不同召回系统的量不同
        # 平滑参数的作用,放大差距
        # 注意,这里召回的是chunkID和Score
        candidate_k = top_k * 2
        hits = self._hybrid_search.search(query, candidate_k)

        # 3. Reranker 精排
        if with_rerank and hits:
            session = await self._get_session()
            try:
                chunks_orm = await self._fetch_chunks_orm([h.chunk_id for h in hits], session)
                reranked = self._reranker.rerank(query, chunks_orm, top_k=len(chunks_orm))
                # 用 rerank 结果替换 hits, 保留 top_k
                hits = reranked[:top_k]
            finally:
                await session.close()

        # 截断到 top_k
        hits = hits[:top_k]

        # 4. 取 chunk 内容
        # 在这里根据文档的docids,获取引用出处
        chunks = await self._fetch_chunks(hits)

        # 5. 写缓存
        await self._cache.set(query, hits, top_k=top_k, with_rerank=with_rerank)

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
        """从 DB 取 chunk 内容并组装 ChunkWithScore(含文档出处)."""
        if not hits:
            return []
        session = await self._get_session()
        try:
            chunks_orm = await self._fetch_chunks_orm([h.chunk_id for h in hits], session)
            # 按 hits 顺序匹配 ORM
            orm_by_id = {c.id: c for c in chunks_orm}
            # 批量取文档标题作为引用出处(增强信息, 失败不阻塞检索)
            titles: dict[int, str] = {}
            try:
                doc_ids = list({orm.doc_id for orm in chunks_orm if orm.doc_id is not None})
                if doc_ids:
                    titles = await DocumentRepo(session).get_many_titles(doc_ids)
            except Exception as exc:
                logger.warning("retriever.fetch_doc_titles_failed", error=str(exc))
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
                            doc_id=orm.doc_id,
                            doc_title=titles.get(orm.doc_id),
                        )
                    )
            return result
        finally:
            await session.close()
