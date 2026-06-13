"""文档服务 - 上传/列表/删除/重建索引的业务编排.

上传: 校验格式与大小 → sha256 去重 → 存 MinIO → 入 documents 表(pending) → 投递索引任务.
删除: 清理向量/BM25/MinIO 对象 → 删 DB 文档(级联 chunks/entities/relations).
重建: 状态置 pending → 投递 reindex 任务(worker 内部先清理再索引).
"""

import asyncio
import contextlib
import hashlib
import io
import mimetypes
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.core.logging import get_logger
from knowflow.db.repositories.document_repo import DocumentRepo
from knowflow.models.document import Document
from knowflow.schemas.document import DeleteResponse, DocumentInfo, ReindexResponse, UploadResponse
from knowflow.tasks.broker import TaskBroker

logger = get_logger(__name__)


class DocumentService:
    """文档管理服务. 每个请求构造一个实例, 持有当次依赖."""

    def __init__(
        self,
        session: AsyncSession,
        minio: Any,
        broker: TaskBroker | None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.minio = minio
        self.broker = broker
        self.settings = settings or get_settings()
        self._repo = DocumentRepo(session)

    @staticmethod
    def _file_type(file_name: str) -> str:
        """取扩展名(小写, 去点)."""
        return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _source_uri(self, file_name: str) -> str:
        """生成 MinIO 对象 key: documents/{uuid}/{file_name}."""
        return f"documents/{uuid.uuid4().hex}/{file_name}"

    def _validate(self, file_name: str, content: bytes) -> str:
        """校验文件类型与大小, 返回 file_type."""
        file_type = self._file_type(file_name)
        allowed = self.settings.allowed_types
        if file_type not in allowed:
            raise ValidationError(
                f"不支持的文件类型: {file_type or '(无扩展名)'}, 允许: {','.join(allowed)}"
            )
        if len(content) > self.settings.upload_max_bytes:
            raise ValidationError(
                f"文件过大: {len(content)} bytes, 上限 {self.settings.upload_max_bytes} bytes"
            )
        return file_type

    async def upload(self, file_name: str, content: bytes, user_id: str) -> UploadResponse:
        """上传文档: 校验 → 去重 → 存 MinIO → 入库 → 投递索引任务."""
        assert self.broker is not None, "upload 需要 broker"
        file_type = self._validate(file_name, content)
        content_hash = self._sha256(content)

        # 秒传去重: 已存在同 hash 的文档直接返回(不重复存储/索引)
        existing = await self._repo.find_by_content_hash(content_hash)
        if existing is not None:
            logger.info("document.dedup_hit", doc_id=existing.id, hash=content_hash)
            return UploadResponse(
                doc_id=existing.id,
                title=existing.title,
                status=existing.status,
                duplicated=True,
                message="文件已存在, 跳过重复索引",
            )

        source_uri = self._source_uri(file_name)
        content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
        # MinIO 客户端为同步, 放线程池避免阻塞事件循环
        await asyncio.to_thread(
            self.minio.put_object,
            self.settings.minio_bucket,
            source_uri,
            io.BytesIO(content),
            len(content),
            content_type,
        )

        doc = await self._repo.create(
            title=file_name,
            source_uri=source_uri,
            file_type=file_type,
            size_bytes=len(content),
            user_id=user_id,
            content_hash=content_hash,
            status="pending",
        )
        await self.session.flush()  # 先取 doc.id 用于投递, 提交留到投递成功之后
        try:
            await self.broker.enqueue(
                self.settings.task_stream_index,
                {"task": "index", "doc_id": doc.id, "attempts": 0},
            )
        except Exception:
            # 投递失败: 不 commit(会话退出时回滚), 并清理已写入的 MinIO 对象,
            # 保持上传原子性 —— 同内容重传可重新走完整流程
            with contextlib.suppress(Exception):
                await asyncio.to_thread(
                    self.minio.remove_object, self.settings.minio_bucket, source_uri
                )
            raise
        await self.session.commit()
        logger.info("document.uploaded", doc_id=doc.id, file_name=file_name, size=len(content))
        return UploadResponse(doc_id=doc.id, title=doc.title, status=doc.status)

    async def list(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> tuple[list[DocumentInfo], int]:
        """分页列出文档(按 user_id)."""
        docs = await self._repo.list_by_user(user_id, limit=limit, offset=offset)
        total = await self._repo.count_by_user(user_id)
        items = [self._to_info(d) for d in docs]
        return items, total

    async def delete(self, doc_id: int) -> DeleteResponse:
        """删除文档: 清理向量/BM25/MinIO → 删 DB(级联)."""
        doc = await self._repo.get(doc_id)
        if doc is None:
            raise NotFoundError(f"文档不存在: doc_id={doc_id}")

        # 清理向量库与 BM25(best-effort, 失败不阻塞删除; 依赖未初始化时跳过)
        try:
            from knowflow.retrieval.bm25_store import get_bm25_store
            from knowflow.retrieval.vector_store import VectorStore

            VectorStore().delete_by_doc(doc_id)
            get_bm25_store().delete_by_doc(doc_id)
        except Exception as exc:
            logger.warning("document.delete_index_cleanup_failed", doc_id=doc_id, error=str(exc))

        # 删 MinIO 对象(best-effort)
        try:
            await asyncio.to_thread(
                self.minio.remove_object, self.settings.minio_bucket, doc.source_uri
            )
        except Exception as exc:
            logger.warning("document.delete_minio_failed", doc_id=doc_id, error=str(exc))

        deleted = await self._repo.delete(doc_id)
        await self.session.commit()
        return DeleteResponse(doc_id=doc_id, deleted=deleted)

    async def reindex(self, doc_id: int) -> ReindexResponse:
        """重建索引: 状态置 pending → 投递 reindex 任务."""
        assert self.broker is not None, "reindex 需要 broker"
        doc = await self._repo.get(doc_id)
        if doc is None:
            raise NotFoundError(f"文档不存在: doc_id={doc_id}")
        await self._repo.update_status(doc_id, "pending")
        await self.session.commit()
        await self.broker.enqueue(
            self.settings.task_stream_index,
            {"task": "reindex", "doc_id": doc_id, "attempts": 0},
        )
        logger.info("document.reindex_queued", doc_id=doc_id)
        return ReindexResponse(doc_id=doc_id, status="pending")

    @staticmethod
    def _to_info(doc: Document) -> DocumentInfo:
        return DocumentInfo(
            id=doc.id,
            title=doc.title,
            file_type=doc.file_type,
            status=doc.status,
            size_bytes=doc.size_bytes,
            content_hash=doc.content_hash,
            user_id=doc.user_id,
            error_message=doc.error_message,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
