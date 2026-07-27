"""知识检索端点 - POST /knowledge/search 调 HybridRetriever.

只读检索, 不写库. 返回 top_k 检索结果(含 chunk 内容/分数/来源).
"""

from fastapi import APIRouter

from knowflow.api.deps import RetrieverDep
from knowflow.schemas.common import ApiResponse
from knowflow.schemas.knowledge import (
    ChunkResult,
    SearchRequest,
    SearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=ApiResponse[SearchResponse])
async def search(
    req: SearchRequest,
    retriever: RetrieverDep,
) -> ApiResponse[SearchResponse]:
    """知识检索: hybrid → rerank → 缓存."""
    result = await retriever.retrieve(
        req.query,
        top_k=req.top_k,
        with_rerank=req.with_rerank,
    )
    chunks = [
        ChunkResult(
            chunk_id=c.chunk_id,
            content=c.content,
            score=c.score,
            source=c.source,
            doc_id=c.doc_id,
            doc_title=c.doc_title,
        )
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
