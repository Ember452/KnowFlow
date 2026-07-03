"""知识检索 Schema - 检索请求/响应/单条 chunk 结果.

对齐 retrieval/retriever.py: RetrievalResult(chunks: list[ChunkWithScore], query,
latency_ms, cache_hit), ChunkWithScore(chunk_id/content/score/source).
"""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """知识检索请求."""

    query: str = Field(min_length=1, max_length=2000, description="查询文本")
    top_k: int | None = Field(default=None, ge=1, le=50, description="返回条数, 默认取配置")
    with_expand: bool = Field(default=True, description="是否启用一跳扩展")
    with_rerank: bool = Field(default=True, description="是否启用 Reranker 精排")


class ChunkResult(BaseModel):
    """单条检索结果."""

    chunk_id: int
    content: str
    score: float
    source: str = Field(description="来源: hybrid/expand/rerank")


class SearchResponse(BaseModel):
    """检索响应."""

    query: str
    chunks: list[ChunkResult] = Field(default_factory=list)
    latency_ms: float = 0.0
    cache_hit: bool = False
    total: int = Field(default=0, description="命中条数")


class GraphNode(BaseModel):
    """图谱节点(实体)."""

    id: int
    name: str
    entity_type: str
    normalized: str
    doc_id: int
    chunk_id: int


class GraphEdge(BaseModel):
    """图谱边(关系). source/target 为实体 id."""

    id: int
    source: int = Field(description="源实体 id")
    target: int = Field(description="目标实体 id")
    relation_type: str
    confidence: float = 1.0
    doc_id: int


class GraphResponse(BaseModel):
    """知识图谱响应: 节点 + 边."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    total: int = Field(default=0, description="实体总数")
