"""知识检索 Schema - 检索请求/响应/单条 chunk 结果.

对齐 retrieval/retriever.py: RetrievalResult(chunks: list[ChunkWithScore], query,
latency_ms, cache_hit), ChunkWithScore(chunk_id/content/score/source).
"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """知识检索请求."""

    query: str = Field(min_length=1, max_length=2000, description="查询文本")
    top_k: int | None = Field(default=None, ge=1, le=50, description="返回条数, 默认取配置")
    with_rerank: bool = Field(default=True, description="是否启用 Reranker 精排")


class ChunkResult(BaseModel):
    """单条检索结果(含文档出处)."""

    chunk_id: int
    content: str
    score: float
    source: str = Field(description="来源: hybrid/rerank")
    doc_id: int | None = Field(default=None, description="所属文档 id")
    doc_title: str | None = Field(default=None, description="所属文档标题")


class SearchResponse(BaseModel):
    """检索响应."""

    query: str
    chunks: list[ChunkResult] = Field(default_factory=list)
    latency_ms: float = 0.0
    cache_hit: bool = False
    total: int = Field(default=0, description="命中条数")
