"""知识检索端点 - POST /knowledge/search 调 GraphRAGRetriever.

只读检索, 不写库. 返回 top_k 检索结果(含 chunk 内容/分数/来源).
"""

from fastapi import APIRouter, Query

from knowflow.api.deps import DbDep, RetrieverDep
from knowflow.db.repositories.graph_repo import EntityRepo, RelationRepo
from knowflow.schemas.common import ApiResponse
from knowflow.schemas.knowledge import (
    ChunkResult,
    GraphEdge,
    GraphNode,
    GraphResponse,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=ApiResponse[SearchResponse])
async def search(
    req: SearchRequest,
    retriever: RetrieverDep,
) -> ApiResponse[SearchResponse]:
    """知识检索: hybrid → expand → rerank → 缓存."""
    result = await retriever.retrieve(
        req.query,
        top_k=req.top_k,
        with_expand=req.with_expand,
        with_rerank=req.with_rerank,
    )
    chunks = [
        ChunkResult(chunk_id=c.chunk_id, content=c.content, score=c.score, source=c.source)
        for c in result.chunks
    ]
    return ApiResponse(
        data=SearchResponse(
            query=result.query,
            chunks=chunks,
            latency_ms=result.latency_ms,
            cache_hit=result.cache_hit,
            total=len(chunks),
        )
    )


@router.get("/graph", response_model=ApiResponse[GraphResponse])
async def get_graph(
    db: DbDep,
    doc_id: int | None = Query(default=None, description="按文档筛选, 为空取全库"),
    limit: int = Query(default=200, ge=1, le=1000, description="实体上限"),
) -> ApiResponse[GraphResponse]:
    """知识图谱: 实体节点 + 关系边(悬空边已过滤). 供前端力导向可视化."""
    entity_repo = EntityRepo(db)
    relation_repo = RelationRepo(db)
    if doc_id is not None:
        entities = await entity_repo.list_by_doc(doc_id, limit=limit)
        relations = await relation_repo.list_by_doc(doc_id, limit=limit * 2)
    else:
        entities = await entity_repo.list_all(limit=limit)
        relations = await relation_repo.list_all(limit=limit * 2)
    entity_ids = {e.id for e in entities}
    nodes = [
        GraphNode(
            id=e.id,
            name=e.name,
            entity_type=e.entity_type,
            normalized=e.normalized,
            doc_id=e.doc_id,
            chunk_id=e.chunk_id,
        )
        for e in entities
    ]
    edges = [
        GraphEdge(
            id=r.id,
            source=r.source_entity_id,
            target=r.target_entity_id,
            relation_type=r.relation_type,
            confidence=r.confidence,
            doc_id=r.doc_id,
        )
        for r in relations
        if r.source_entity_id in entity_ids and r.target_entity_id in entity_ids
    ]
    return ApiResponse(data=GraphResponse(nodes=nodes, edges=edges, total=len(nodes)))
