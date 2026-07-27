"""索引任务处理 - 消费索引/重建任务, 组装 IndexDeps 调 RetrievalPipeline.

任务 payload: {"task": "index"|"reindex", "doc_id": int, "attempts": int}
- index: 首次索引(文档刚上传)
- reindex: 重建索引(先清理向量/BM25/chunks 再索引)

依赖外部单例: PG session factory / MinIO / Milvus / Embedding /
BM25Store(启动时从 chunks 表全量加载). 进程内增量写入不跨进程同步, 重启后恢复一致.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import get_settings
from knowflow.core.exceptions import NotFoundError
from knowflow.core.logging import get_logger
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.retrieval.bm25_store import get_bm25_store
from knowflow.retrieval.embedding import get_embedding_client
from knowflow.retrieval.pipeline import IndexDeps, IndexError, RetrievalPipeline
from knowflow.retrieval.vector_store import VectorStore

logger = get_logger(__name__)

# 构造依赖的工厂签名: 接收 AsyncSession 返回 IndexDeps
DepsFactory = Callable[[AsyncSession], IndexDeps]


def build_index_deps(session: AsyncSession) -> IndexDeps:
    """从全局单例构造索引依赖(生产路径)."""
    settings = get_settings()
    return IndexDeps(
        session=session,
        document_repo=DocumentRepo(session),
        chunk_repo=ChunkRepo(session),
        document_index_repo=DocumentIndexRepo(session),
        vector_store=VectorStore(),
        bm25_store=get_bm25_store(),
        embedding_client=get_embedding_client(),
        minio_client=_get_minio_sync(),
        bucket=settings.minio_bucket,
    )


def _get_minio_sync() -> Any:
    """取 MinIO 单例(同步客户端)."""
    from knowflow.db.minio import get_minio

    return get_minio()


async def handle_index_task(payload: dict[str, Any], build_deps: DepsFactory) -> dict[str, Any]:
    """处理单条索引任务.

    Returns:
        {"ok": bool, "retryable": bool, "doc_id": int, "result": IndexResult | None}
    """
    task = payload.get("task", "index")
    doc_id = payload.get("doc_id")
    if doc_id is None:
        logger.error("index_task.missing_doc_id", payload=payload)
        return {"ok": False, "retryable": False, "doc_id": None, "result": None}

    # 每个任务一个独立 session(pipeline 内部 commit)
    from knowflow.db.base import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        deps = build_deps(session)
        pipeline = RetrievalPipeline(deps)
        try:
            if task == "reindex":
                result = await pipeline.reindex_document(int(doc_id))
            else:
                result = await pipeline.index_document(int(doc_id))
            logger.info(
                "index_task.done",
                task=task,
                doc_id=doc_id,
                chunks=result.chunk_count,
            )
            return {"ok": True, "retryable": False, "doc_id": int(doc_id), "result": result}
        except NotFoundError as exc:
            # 文档不存在, 重试无意义
            logger.warning("index_task.not_found", doc_id=doc_id, error=str(exc))
            return {"ok": False, "retryable": False, "doc_id": int(doc_id), "result": None}
        except IndexError as exc:
            logger.error("index_task.failed", doc_id=doc_id, error=str(exc))
            return {"ok": False, "retryable": True, "doc_id": int(doc_id), "result": None}
