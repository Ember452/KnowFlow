"""Hybrid Search - 向量召回 + BM25 召回 + RRF 融合.

RRF (Reciprocal Rank Fusion) 公式:
    score(d) = sum over rankings of 1 / (k + rank(d))

其中 k 是平滑参数(默认 60), rank 是文档在该路召回中的排名(从 1 开始).
RRF 的优势: 不依赖原始分数的绝对值, 只看排名, 适合融合不同量度的召回器.
"""

from dataclasses import dataclass

from knowflow.core.config import get_settings
from knowflow.core.constants import RRF_K
from knowflow.retrieval.bm25_store import BM25Hit, BM25Store
from knowflow.retrieval.embedding import EmbeddingClient
from knowflow.retrieval.vector_store import VectorHit, VectorStore


@dataclass(frozen=True)
class ChunkScore:
    """检索结果条目(含分数与来源)."""

    chunk_id: int
    score: float
    source: str  # "hybrid" / "expand" / "rerank"


class HybridSearch:
    """混合检索: 向量 + BM25 双路召回, RRF 融合."""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_store: BM25Store,
        embedding_client: EmbeddingClient,
        *,
        rrf_k: int | None = None,
    ) -> None:
        """初始化.

        Args:
            vector_store: 向量存储客户端.
            bm25_store: BM25 内存索引.
            embedding_client: Embedding 客户端(用于 query 向量化).
            rrf_k: RRF 平滑参数, None 时取 settings.rrf_k.
        """
        self.vector_store = vector_store
        self.bm25_store = bm25_store
        self.embedding_client = embedding_client
        self.rrf_k = rrf_k if rrf_k is not None else get_settings().rrf_k

    def search(self, query: str, top_k: int) -> list[ChunkScore]:
        """混合检索.

        Args:
            query: 查询文本.
            top_k: 返回条数.

        Returns:
            ChunkScore 列表, 按 RRF 融合分数降序, source="hybrid".
        """
        if not query or top_k <= 0:
            return []

        # 双路召回(各取 top_k, 保证两路都有足够候选)
        query_vec = self.embedding_client.embed_one(query)
        vector_hits: list[VectorHit] = (
            self.vector_store.search(query_vec, top_k) if query_vec else []
        )
        bm25_hits = self.bm25_store.search(query, top_k)

        return self.fuse(vector_hits, bm25_hits, top_k=top_k, k=self.rrf_k)

    @staticmethod
    def fuse(
        vector_hits: list[VectorHit],
        bm25_hits: list[BM25Hit],
        *,
        top_k: int,
        k: int = RRF_K,
    ) -> list[ChunkScore]:
        """RRF 融合两路召回结果.

        Args:
            vector_hits: 向量召回结果.
            bm25_hits: BM25 召回结果.
            top_k: 返回条数.
            k: RRF 平滑参数, 默认 60.

        Returns:
            ChunkScore 列表, 按 RRF 分数降序, source="hybrid".
        """
        scores: dict[int, float] = {}

        # 向量路: rank 从 1 开始
        for rank, v_hit in enumerate(vector_hits, start=1):
            scores[v_hit.chunk_id] = scores.get(v_hit.chunk_id, 0.0) + 1.0 / (k + rank)

        # BM25 路
        for rank, b_hit in enumerate(bm25_hits, start=1):
            scores[b_hit.chunk_id] = scores.get(b_hit.chunk_id, 0.0) + 1.0 / (k + rank)

        # 按融合分数降序取 top_k
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            ChunkScore(chunk_id=cid, score=score, source="hybrid")
            for cid, score in sorted_ids[:top_k]
        ]
