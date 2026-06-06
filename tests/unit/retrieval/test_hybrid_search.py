"""hybrid_search 单测 - 重点测 RRF 融合算法, mock 两路召回返回固定 hits."""

from knowflow.retrieval.bm25_store import BM25Hit
from knowflow.retrieval.hybrid_search import HybridSearch
from knowflow.retrieval.vector_store import VectorHit

# ── RRF 融合算法单测(HybridSearch.fuse 静态方法) ──


def test_fuse_empty_inputs() -> None:
    """两路都空时返回空列表."""
    assert HybridSearch.fuse([], [], top_k=10) == []


def test_fuse_single_vector_only() -> None:
    """仅向量路命中时, RRF 分数 = 1/(k+rank)."""
    vector_hits = [VectorHit(chunk_id=1, score=0.9), VectorHit(chunk_id=2, score=0.8)]
    result = HybridSearch.fuse(vector_hits, [], top_k=10, k=60)
    assert len(result) == 2
    assert result[0].chunk_id == 1  # rank 1, 分数更高
    assert result[0].score == 1.0 / (60 + 1)
    assert result[1].chunk_id == 2
    assert result[1].score == 1.0 / (60 + 2)
    assert all(r.source == "hybrid" for r in result)


def test_fuse_single_bm25_only() -> None:
    """仅 BM25 路命中时, RRF 分数 = 1/(k+rank)."""
    bm25_hits = [BM25Hit(chunk_id=3, score=2.5), BM25Hit(chunk_id=4, score=1.8)]
    result = HybridSearch.fuse([], bm25_hits, top_k=10, k=60)
    assert len(result) == 2
    assert result[0].chunk_id == 3
    assert result[0].score == 1.0 / (60 + 1)
    assert result[1].chunk_id == 4
    assert result[1].score == 1.0 / (60 + 2)


def test_fuse_dual_path_overlap() -> None:
    """双路命中同一 chunk 时, RRF 分数累加."""
    # chunk 1 在两路都排第一
    vector_hits = [VectorHit(chunk_id=1, score=0.9), VectorHit(chunk_id=2, score=0.8)]
    bm25_hits = [BM25Hit(chunk_id=1, score=2.5), BM25Hit(chunk_id=3, score=1.0)]
    result = HybridSearch.fuse(vector_hits, bm25_hits, top_k=10, k=60)

    # chunk 1 分数 = 1/61 + 1/61 = 2/61, 应排第一
    assert result[0].chunk_id == 1
    assert result[0].score == 2.0 / (60 + 1)
    # chunk 2 和 chunk 3 各占一路, 分数 = 1/62
    assert result[1].score == 1.0 / (60 + 2)
    assert result[2].score == 1.0 / (60 + 2)


def test_fuse_top_k_truncation() -> None:
    """top_k 截断: 返回不超过 top_k 条."""
    vector_hits = [VectorHit(chunk_id=i, score=0.1 * i) for i in range(1, 6)]
    result = HybridSearch.fuse(vector_hits, [], top_k=3, k=60)
    assert len(result) == 3


def test_fuse_custom_k() -> None:
    """自定义 k 参数影响分数."""
    vector_hits = [VectorHit(chunk_id=1, score=0.9)]
    result_k60 = HybridSearch.fuse(vector_hits, [], top_k=1, k=60)
    result_k10 = HybridSearch.fuse(vector_hits, [], top_k=1, k=10)
    # k 越小, 分数越大
    assert result_k10[0].score > result_k60[0].score
    assert result_k60[0].score == 1.0 / 61
    assert result_k10[0].score == 1.0 / 11


def test_fuse_order_preserved() -> None:
    """融合后按分数降序排列."""
    vector_hits = [
        VectorHit(chunk_id=1, score=0.9),
        VectorHit(chunk_id=2, score=0.8),
        VectorHit(chunk_id=3, score=0.7),
    ]
    bm25_hits = [
        BM25Hit(chunk_id=3, score=2.0),
        BM25Hit(chunk_id=2, score=1.0),
        BM25Hit(chunk_id=1, score=0.5),
    ]
    result = HybridSearch.fuse(vector_hits, bm25_hits, top_k=10, k=60)
    # 三条都双路命中, 分数都是 1/61 + 1/62 但 rank 不同
    # chunk 1: 1/61 + 1/63
    # chunk 2: 1/62 + 1/62
    # chunk 3: 1/63 + 1/61
    # chunk 1 和 chunk 3 分数相同(对称), chunk 2 略不同
    scores = [r.score for r in result]
    assert scores == sorted(scores, reverse=True)


# ── HybridSearch.search 集成测试(mock 子组件) ──


class FakeVectorStore:
    """fake VectorStore."""

    def __init__(self, hits: list[VectorHit]) -> None:
        self.hits = hits
        self.search_calls: list[tuple[list[float], int]] = []

    def search(self, query_vector: list[float], top_k: int) -> list[VectorHit]:
        self.search_calls.append((query_vector, top_k))
        return self.hits


class FakeBM25Store:
    """fake BM25Store."""

    def __init__(self, hits: list[BM25Hit]) -> None:
        self.hits = hits
        self.search_calls: list[tuple[str, int]] = []

    def search(self, query: str, top_k: int) -> list[BM25Hit]:
        self.search_calls.append((query, top_k))
        return self.hits


class FakeEmbeddingClient:
    """fake EmbeddingClient."""

    def __init__(self, vec: list[float] | None = None) -> None:
        self.vec = vec if vec is not None else [0.1, 0.2, 0.3]

    def embed_one(self, text: str) -> list[float]:
        return self.vec if text else []


def test_search_invokes_both_stores() -> None:
    """search 同时调用向量与 BM25 两路."""
    vec_store = FakeVectorStore([VectorHit(chunk_id=1, score=0.9)])
    bm25_store = FakeBM25Store([BM25Hit(chunk_id=2, score=1.5)])
    emb = FakeEmbeddingClient()
    hs = HybridSearch(vec_store, bm25_store, emb, rrf_k=60)

    result = hs.search("test query", top_k=5)
    assert len(result) == 2  # 两路各 1 条
    assert vec_store.search_calls[0][1] == 5  # top_k 透传
    assert bm25_store.search_calls[0][1] == 5
    assert emb.embed_one  # 验证 embedding 被调用


def test_search_empty_query() -> None:
    """空查询返回空列表, 不调任何子组件."""
    vec_store = FakeVectorStore([])
    bm25_store = FakeBM25Store([])
    emb = FakeEmbeddingClient()
    hs = HybridSearch(vec_store, bm25_store, emb)

    assert hs.search("", top_k=5) == []
    assert vec_store.search_calls == []
    assert bm25_store.search_calls == []


def test_search_top_k_zero() -> None:
    """top_k <= 0 返回空列表."""
    hs = HybridSearch(FakeVectorStore([]), FakeBM25Store([]), FakeEmbeddingClient())
    assert hs.search("test", top_k=0) == []


def test_search_embedding_returns_empty() -> None:
    """embedding 返回空时, 向量路跳过, 仅 BM25 路."""
    vec_store = FakeVectorStore([VectorHit(chunk_id=1, score=0.9)])
    bm25_store = FakeBM25Store([BM25Hit(chunk_id=2, score=1.5)])
    emb = FakeEmbeddingClient(vec=[])  # 空向量
    hs = HybridSearch(vec_store, bm25_store, emb)

    result = hs.search("test", top_k=5)
    # 仅 BM25 路 1 条
    assert len(result) == 1
    assert result[0].chunk_id == 2
    assert vec_store.search_calls == []  # 向量路未调用
