"""文档端点 - 上传/列表/删除/重建索引.

上传先落 MinIO 原始文件, 入 documents 表(pending), 投递异步索引任务由 worker 消费.
"""

from typing import Annotated

from fastapi import APIRouter, File, Query, UploadFile
from sqlalchemy.exc import SQLAlchemyError

from knowflow.api.deps import BrokerDep, DbDep, MinioDep, UserDep
from knowflow.core.exceptions import AppError
from knowflow.core.logging import get_logger
from knowflow.schemas.common import ApiResponse, PageResponse
from knowflow.schemas.document import (
    DeleteResponse,
    DocumentInfo,
    ReindexResponse,
    UploadResponse,
)
from knowflow.services.document_service import DocumentService

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["document"])

UploadFileDep = Annotated[UploadFile, File(description="待上传文件(pdf/docx/md/txt)")]
LimitDep = Annotated[int, Query(ge=1, le=200)]
OffsetDep = Annotated[int, Query(ge=0)]


@router.post("/upload", response_model=ApiResponse[UploadResponse])
async def upload_document(
    file: UploadFileDep,
    db: DbDep,
    minio: MinioDep,
    broker: BrokerDep,
    user_id: UserDep,
) -> ApiResponse[UploadResponse]:
    """上传文档. 校验格式/大小 → 去重 → 存 MinIO → 入库 → 投递索引任务."""
    content = await file.read()
    service = DocumentService(session=db, minio=minio, broker=broker)
    try:
        resp = await service.upload(file.filename or "untitled", content, user_id)
    except AppError:
        raise
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.error("document.upload_db_error", error=str(exc))
        raise AppError(message="文档入库失败", status_code=500, error_code="DB-001") from exc
    return ApiResponse(data=resp)


@router.get("", response_model=ApiResponse[PageResponse[DocumentInfo]])
async def list_documents(
    db: DbDep,
    user_id: UserDep,
    limit: LimitDep = 50,
    offset: OffsetDep = 0,
) -> ApiResponse[PageResponse[DocumentInfo]]:
    """分页列出当前用户的文档."""
    service = DocumentService(session=db, minio=None, broker=None)
    items, total = await service.list(user_id, limit=limit, offset=offset)
    return ApiResponse(data=PageResponse(items=items, total=total, limit=limit, offset=offset))


@router.delete("/{doc_id}", response_model=ApiResponse[DeleteResponse])
async def delete_document(
    doc_id: int,
    db: DbDep,
    minio: MinioDep,
    broker: BrokerDep,
    user_id: UserDep,
) -> ApiResponse[DeleteResponse]:
    """删除文档及索引(仅属主可操作)."""
    service = DocumentService(session=db, minio=minio, broker=broker)
    resp = await service.delete(doc_id, user_id)
    return ApiResponse(data=resp)


@router.post("/{doc_id}/reindex", response_model=ApiResponse[ReindexResponse])
async def reindex_document(
    doc_id: int,
    db: DbDep,
    minio: MinioDep,
    broker: BrokerDep,
    user_id: UserDep,
) -> ApiResponse[ReindexResponse]:
    """重建文档索引(先清理后重建, 仅属主可操作)."""
    service = DocumentService(session=db, minio=minio, broker=broker)
    resp = await service.reindex(doc_id, user_id)
    return ApiResponse(data=resp)
