"""索引编排 pipeline - 串联解析→分块→embedding→实体抽取→三写入库.

完整链路:
    DocumentRepo.get(doc_id) -> MinIO 下载 -> parser.parse -> splitter.split
    -> DocumentRepo.update_status("indexing")
    -> 逐块: ChunkRepo.create -> embedding.embed_one -> VectorStore.upsert -> BM25Store.add_batch
    -> 逐块: entity_extractor.extract -> GraphStore.upsert_entities + upsert_relations
    -> DocumentRepo.update_status("ready") + DocumentIndexRepo.upsert(vector/graph/bm25)

异常时 update_status("failed", error_message) 并抛 IndexError.
reindex_document 先清理向量/BM25/chunks(DB 级联 entities/relations) 再调 index_document.
"""

import contextlib
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import get_settings
from knowflow.core.exceptions import AppError, NotFoundError
from knowflow.core.logging import get_logger
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.models.document import Chunk
from knowflow.retrieval.bm25_store import BM25Doc, BM25Store
from knowflow.retrieval.embedding import EmbeddingClient
from knowflow.retrieval.entity_extractor import EntityExtractor
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.vector_store import ChunkVector, VectorStore

logger = get_logger(__name__)


class IndexError(AppError):
    """索引失败."""

    error_code = "RETR-002"
    status_code = 500
    default_message = "索引失败"


@dataclass(frozen=True)
class IndexResult:
    """索引结果."""

    doc_id: int
    chunk_count: int = 0
    entity_count: int = 0
    relation_count: int = 0
    duration_ms: float = 0.0


@dataclass
class IndexDeps:
    """索引依赖容器, 便于构造与单测注入."""

    session: AsyncSession
    document_repo: DocumentRepo
    chunk_repo: ChunkRepo
    document_index_repo: DocumentIndexRepo
    graph_store: GraphStore
    vector_store: VectorStore
    bm25_store: BM25Store
    embedding_client: EmbeddingClient
    entity_extractor: EntityExtractor
    minio_client: Any
    bucket: str = ""
    parse_fn: Callable[..., str] | None = None
    split_fn: Callable[..., list[str]] | None = None


class RetrievalPipeline:
    """索引编排 pipeline. 串联解析→分块→embedding→实体抽取→三写入库."""

    def __init__(self, deps: IndexDeps) -> None:
        """初始化.

        Args:
            deps: 索引依赖容器.
        """
        self.deps = deps
        settings = get_settings()
        self._chunk_size = settings.chunk_size
        self._chunk_overlap = settings.chunk_overlap
        self._bucket = deps.bucket or settings.minio_bucket

    async def index_document(self, doc_id: int) -> IndexResult:
        """索引单个文档.

        Args:
            doc_id: 文档 id.

        Returns:
            IndexResult, 含 chunk/entity/relation 计数与耗时.

        Raises:
            NotFoundError: 文档不存在.
            IndexError: 索引失败(状态已置 failed).
        """
        start = time.perf_counter()
        doc = await self.deps.document_repo.get(doc_id)
        if doc is None:
            raise NotFoundError(f"文档不存在: doc_id={doc_id}")

        try:
            # 1. 下载 + 解析
            text = self._fetch_text(doc.source_uri, doc.file_type)

            # 2. 分块
            if self.deps.split_fn is not None:
                chunks_text = self.deps.split_fn(
                    text, chunk_size=self._chunk_size, overlap=self._chunk_overlap
                )
            else:
                from knowflow.retrieval.indexer.splitter import split

                chunks_text = split(text, chunk_size=self._chunk_size, overlap=self._chunk_overlap)

            # 3. 状态置 indexing
            await self.deps.document_repo.update_status(doc_id, "indexing")
            await self.deps.session.commit()

            # 4. 逐块: chunk + embedding + vector + bm25
            chunk_orms: list[Chunk] = []
            chunk_vectors: list[ChunkVector] = []
            bm25_docs: list[BM25Doc] = []
            for i, ct in enumerate(chunks_text):
                token_count = len(ct)  # 简化: 字符数近似 token 数
                chunk = await self.deps.chunk_repo.create(
                    doc_id=doc_id,
                    content=ct,
                    chunk_index=i,
                    token_count=token_count,
                )
                chunk_orms.append(chunk)
                vec = self.deps.embedding_client.embed_one(ct)
                chunk_vectors.append(ChunkVector(chunk_id=chunk.id, doc_id=doc_id, embedding=vec))
                bm25_docs.append(BM25Doc(chunk_id=chunk.id, content=ct, doc_id=doc_id))

            if chunk_vectors:
                self.deps.vector_store.upsert(chunk_vectors)
            if bm25_docs:
                self.deps.bm25_store.add_batch(bm25_docs)

            # 5. 逐块: 实体抽取 + 图谱写入
            total_entities = 0
            total_relations = 0
            all_name_to_id: dict[str, int] = {}
            for chunk in chunk_orms:
                extract = self.deps.entity_extractor.extract(chunk.content)
                if extract.entities:
                    orm_ents = await self.deps.graph_store.upsert_entities(
                        doc_id, chunk.id, extract.entities
                    )
                    for e in orm_ents:
                        all_name_to_id[e.name] = e.id
                    total_entities += len(orm_ents)
                if extract.relations:
                    orm_rels = await self.deps.graph_store.upsert_relations(
                        doc_id, extract.relations, all_name_to_id
                    )
                    total_relations += len(orm_rels)

            # 6. 写索引状态 + 状态置 ready
            for it in ("vector", "graph", "bm25"):
                await self.deps.document_index_repo.upsert(
                    doc_id=doc_id, index_type=it, status="ready"
                )
            await self.deps.document_repo.update_status(doc_id, "ready")
            await self.deps.session.commit()

            duration_ms = (time.perf_counter() - start) * 1000
            return IndexResult(
                doc_id=doc_id,
                chunk_count=len(chunk_orms),
                entity_count=total_entities,
                relation_count=total_relations,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            await self.deps.document_repo.update_status(doc_id, "failed", error_message=str(exc))
            await self.deps.session.commit()
            logger.error("pipeline.index_failed", doc_id=doc_id, error=str(exc))
            raise IndexError(f"索引失败: doc_id={doc_id}: {exc}") from exc

    def _fetch_text(self, source_uri: str, file_type: str) -> str:
        """从 MinIO 下载文件并解析为纯文本.

        Args:
            source_uri: MinIO 对象 key.
            file_type: 文件类型(用于临时文件后缀, 决定 parser 分发).

        Returns:
            清洗后的纯文本.
        """
        suffix = f".{file_type}" if file_type else ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tf:
            temp_path = tf.name
        try:
            self.deps.minio_client.fget_object(self._bucket, source_uri, temp_path)
            if self.deps.parse_fn is not None:
                text: str = self.deps.parse_fn(temp_path)
                return text
            from knowflow.retrieval.indexer.parser import parse

            parsed: str = parse(temp_path)
            return parsed
        finally:
            with contextlib.suppress(OSError):
                os.unlink(temp_path)

    async def reindex_document(self, doc_id: int) -> IndexResult:
        """重建索引: 清理三路索引后重新索引.

        步骤:
            1. VectorStore.delete_by_doc + BM25Store.delete_by_doc
            2. DB 删除 chunks(外键级联清理 entities/relations)
            3. 调 index_document 重新索引

        Args:
            doc_id: 文档 id.

        Returns:
            IndexResult.
        """
        self.deps.vector_store.delete_by_doc(doc_id)
        self.deps.bm25_store.delete_by_doc(doc_id)
        await self.deps.session.execute(delete(Chunk).where(Chunk.doc_id == doc_id))
        await self.deps.session.commit()
        return await self.index_document(doc_id)
