"""retriever 单测 - mock 各子组件, 验证缓存命中跳过 / 调用顺序 / 开关."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest

from knowflow.retrieval.hybrid_search import ChunkScore
from knowflow.retrieval.retriever import (
    ChunkWithScore,
    GraphRAGRetriever,
    RetrievalResult,
)


@dataclass
class FakeChunk:
    """fake Chunk ORM."""

    id: int
    content: str
    doc_id: int = 0


class FakeSession:
    """fake AsyncSession, 模拟 close 与 execute(标题查询返回预设 titles)."""

    def __init__(self, titles: dict[int, str] | None = None) -> None:
        self.closed = False
        self.titles = titles or {}
        self.executes: list[Any] = []

    async def close(self) -> None:
        self.closed = True

    async def execute(self, stmt: Any) -> Any:
        self.executes.append(stmt)
        return SimpleNamespace(all=lambda: list(self.titles.items()))


class FakeChunkRepo:
    """fake ChunkRepo, 返回预设 chunk 列表."""

    def __init__(self, chunks: list[FakeChunk]) -> None:
        self.chunks = chunks

    async def get_many(self, chunk_ids: list[int]) -> list[FakeChunk]:
        by_id = {c.id: c for c in self.chunks}
        return [by_id[cid] for cid in chunk_ids if cid in by_id]


class FakeHybridSearch:
    """fake HybridSearch."""

    def __init__(self, hits: list[ChunkScore]) -> None:
        self.hits = hits
        self.search_calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int) -> list[ChunkScore]:
        self.search_calls.append((query, top_k))
        return self.hits


class FakeExpander:
    """fake Expander."""

    def __init__(self, expanded: list[ChunkScore]) -> None:
        self.expanded = expanded
        self.expand_calls: int = 0

    async def expand(self, hits: list[ChunkScore]) -> list[ChunkScore]:
        self.expand_calls += 1
        return self.expanded


class FakeReranker:
    """fake Reranker."""

    def __init__(self, reranked: list[ChunkScore]) -> None:
        self.reranked = reranked
        self.rerank_calls: int = 0

    def rerank(self, query: str, chunks: list, *, top_k: int) -> list[ChunkScore]:
        self.rerank_calls += 1
        return self.reranked


class FakeCache:
    """fake RetrievalCache."""

    def __init__(self, cached: list[ChunkScore] | None = None) -> None:
        self._cached = cached
        self.get_calls: int = 0
        self.get_args: list[tuple[str, int, bool, bool]] = []
        self.set_calls: list[tuple[str, int, bool, bool, list[ChunkScore]]] = []

    async def get(
        self,
        query: str,
        *,
        top_k: int,
        with_expand: bool,
        with_rerank: bool,
    ) -> list[ChunkScore] | None:
        self.get_calls += 1
        self.get_args.append((query, top_k, with_expand, with_rerank))
        return self._cached

    async def set(
        self,
        query: str,
        results: list[ChunkScore],
        *,
        top_k: int,
        with_expand: bool,
        with_rerank: bool,
    ) -> None:
        self.set_calls.append((query, top_k, with_expand, with_rerank, results))


def _make_retriever(
    hybrid_hits: list[ChunkScore] | None = None,
    expanded: list[ChunkScore] | None = None,
    reranked: list[ChunkScore] | None = None,
    cached: list[ChunkScore] | None = None,
    chunks_orm: list[FakeChunk] | None = None,
    titles: dict[int, str] | None = None,
) -> tuple[GraphRAGRetriever, FakeHybridSearch, FakeExpander, FakeReranker, FakeCache]:
    """构造完整 mock 链路的 retriever."""
    hybrid = FakeHybridSearch(hybrid_hits or [])
    expander = FakeExpander(expanded or hybrid_hits or [])
    reranker = FakeReranker(reranked or hybrid_hits or [])
    cache = FakeCache(cached)

    chunks = chunks_orm or [FakeChunk(id=1, content="c1"), FakeChunk(id=2, content="c2")]
    session = FakeSession(titles)

    # 用 lambda 返回 session, 模拟 session_factory
    def session_factory() -> FakeSession:
        return session

    retriever = GraphRAGRetriever(
        session_factory=session_factory,
        hybrid_search=hybrid,
        expander_factory=lambda _session: expander,
        reranker=reranker,
        cache=cache,
    )

    # monkeypatch _fetch_chunks_orm 返回预设 chunk
    async def fake_fetch_chunks_orm(chunk_ids, sess):  # type: ignore[no-untyped-def]
        by_id = {c.id: c for c in chunks}
        return [by_id[cid] for cid in chunk_ids if cid in by_id]

    retriever._fetch_chunks_orm = fake_fetch_chunks_orm  # type: ignore[assignment]

    return retriever, hybrid, expander, reranker, cache


@pytest.mark.asyncio
async def test_retrieve_cache_hit_skips_pipeline() -> None:
    """缓存命中时跳过 hybrid/expand/rerank, 直接返回."""
    cached = [ChunkScore(chunk_id=1, score=0.9, source="hybrid")]
    retriever, hybrid, expander, reranker, cache = _make_retriever(cached=cached)

    result = await retriever.retrieve("query", top_k=5)

    assert result.cache_hit is True
    assert cache.get_calls == 1
    assert hybrid.search_calls == []  # 未调用
    assert expander.expand_calls == 0
    assert reranker.rerank_calls == 0
    # 缓存命中不写缓存
    assert cache.set_calls == []
    assert len(result.chunks) >= 1


@pytest.mark.asyncio
async def test_retrieve_passes_params_to_cache() -> None:
    """缓存 get/set 收到与检索一致的参数(参与缓存键, 参数不一致不得相互命中)."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    retriever, _hybrid, _expander, _reranker, cache = _make_retriever(
        hybrid_hits=hybrid_hits,
        expanded=hybrid_hits,
        reranked=hybrid_hits,
    )

    await retriever.retrieve("query", top_k=7, with_expand=False, with_rerank=True)

    # get 与 set 均使用相同参数
    assert cache.get_args == [("query", 7, False, True)]
    assert len(cache.set_calls) == 1
    assert cache.set_calls[0][1] == 7
    assert cache.set_calls[0][2] is False
    assert cache.set_calls[0][3] is True


@pytest.mark.asyncio
async def test_retrieve_cache_miss_full_pipeline() -> None:
    """缓存未命中时走完整链路: hybrid -> expand -> rerank -> set."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    retriever, hybrid, expander, reranker, cache = _make_retriever(
        hybrid_hits=hybrid_hits,
        expanded=hybrid_hits,
        reranked=hybrid_hits,
    )

    result = await retriever.retrieve("query", top_k=5)

    assert result.cache_hit is False
    assert cache.get_calls == 1
    assert len(hybrid.search_calls) == 1
    assert expander.expand_calls == 1
    assert reranker.rerank_calls == 1
    # 写缓存
    assert len(cache.set_calls) == 1


@pytest.mark.asyncio
async def test_retrieve_with_expand_disabled() -> None:
    """with_expand=False 时跳过一跳扩展."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    retriever, _hybrid, expander, reranker, _cache = _make_retriever(
        hybrid_hits=hybrid_hits,
        reranked=hybrid_hits,
    )

    await retriever.retrieve("query", top_k=5, with_expand=False)

    assert expander.expand_calls == 0
    assert reranker.rerank_calls == 1  # rerank 仍执行


@pytest.mark.asyncio
async def test_retrieve_with_rerank_disabled() -> None:
    """with_rerank=False 时跳过精排."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    retriever, _hybrid, expander, reranker, _cache = _make_retriever(
        hybrid_hits=hybrid_hits,
        expanded=hybrid_hits,
    )

    await retriever.retrieve("query", top_k=5, with_rerank=False)

    assert expander.expand_calls == 1
    assert reranker.rerank_calls == 0


@pytest.mark.asyncio
async def test_retrieve_empty_query() -> None:
    """空查询应正常处理(不抛异常)."""
    retriever, _hybrid, _expander, _reranker, _cache = _make_retriever(
        hybrid_hits=[],
    )

    result = await retriever.retrieve("", top_k=5)
    assert isinstance(result, RetrievalResult)
    assert result.query == ""


@pytest.mark.asyncio
async def test_retrieve_returns_chunk_with_content() -> None:
    """返回的 ChunkWithScore 含 chunk 内容."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    chunks_orm = [FakeChunk(id=1, content="hello world")]
    retriever, *_ = _make_retriever(
        hybrid_hits=hybrid_hits,
        expanded=hybrid_hits,
        reranked=hybrid_hits,
        chunks_orm=chunks_orm,
    )

    result = await retriever.retrieve("query", top_k=5, with_rerank=False)

    assert len(result.chunks) == 1
    assert isinstance(result.chunks[0], ChunkWithScore)
    assert result.chunks[0].content == "hello world"
    assert result.chunks[0].chunk_id == 1


@pytest.mark.asyncio
async def test_retrieve_returns_doc_origin() -> None:
    """返回的 ChunkWithScore 含文档出处 doc_id/doc_title."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    chunks_orm = [FakeChunk(id=1, content="hello world", doc_id=42)]
    retriever, *_ = _make_retriever(
        hybrid_hits=hybrid_hits,
        expanded=hybrid_hits,
        reranked=hybrid_hits,
        chunks_orm=chunks_orm,
        titles={42: "报销手册"},
    )

    result = await retriever.retrieve("query", top_k=5, with_rerank=False)

    assert result.chunks[0].doc_id == 42
    assert result.chunks[0].doc_title == "报销手册"


@pytest.mark.asyncio
async def test_retrieve_latency_recorded() -> None:
    """返回结果含 latency_ms."""
    hybrid_hits = [ChunkScore(chunk_id=1, score=0.5, source="hybrid")]
    retriever, *_ = _make_retriever(
        hybrid_hits=hybrid_hits,
        expanded=hybrid_hits,
        reranked=hybrid_hits,
    )

    result = await retriever.retrieve("query", top_k=5)
    assert result.latency_ms > 0
