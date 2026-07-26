"""索引编排 pipeline - 串联解析→分块→embedding→实体抽取→三写入库.

完整链路:
    DocumentRepo.get(doc_id) -> MinIO 下载 -> parser.parse -> splitter.split
    -> DocumentRepo.update_status("indexing")
    -> embedding.embed(批量推理) -> 逐块: ChunkRepo.create
    -> VectorStore.upsert -> BM25Store.add_batch
    -> 逐块: entity_extractor.extract -> GraphStore.upsert_entities + upsert_relations
    -> DocumentRepo.update_status("ready") + DocumentIndexRepo.upsert(vector/graph/bm25)

异常时 update_status("failed", error_message) 并抛 IndexError.
reindex_document 先清理向量/BM25/chunks(DB 级联 entities/relations) 再调 index_document.
"""

import asyncio
import contextlib
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.context.token_counter import TokenCounter
from knowflow.core.config import get_settings
from knowflow.core.exceptions import AppError, NotFoundError
from knowflow.core.logging import get_logger
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.models.document import Chunk
from knowflow.retrieval.bm25_store import BM25Doc, BM25Store
from knowflow.retrieval.cache import RetrievalCache
from knowflow.retrieval.embedding import EmbeddingClient
from knowflow.retrieval.entity_extractor import EntityExtractor, ExtractResult
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.vector_store import ChunkVector, VectorStore

logger = get_logger(__name__)

# 实体抽取并发度: LLM API 调用并发上限, 防限流的同时把串行等待变为并行
_EXTRACT_CONCURRENCY = 4


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
    retrieval_cache: RetrievalCache | None = None  # 索引成功后失效检索缓存(可注入 fake)


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
        self._token_counter = TokenCounter()
        # 索引成功会改变检索结果, 必须失效旧缓存, 否则返回过期结果
        self._retrieval_cache = deps.retrieval_cache or RetrievalCache()

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
            # 这个优先按照段落切割，如果切割后的长,进行句子切割，最后还不行，降级为固定size切割  # noqa: E501, RUF003
            if self.deps.split_fn is not None:
                chunks_text = self.deps.split_fn(
                    text, chunk_size=self._chunk_size, overlap=self._chunk_overlap
                )
            else:
                from knowflow.retrieval.indexer.splitter import split

                # 如果不成功, 采用简单在字符分块
                chunks_text = split(text, chunk_size=self._chunk_size, overlap=self._chunk_overlap)

            # 3. 状态置 indexing
            await self.deps.document_repo.update_status(doc_id, "indexing")
            await self.deps.session.commit()

            # 4. embedding 批量推理(内部按 batch_size 切片), 逐块写库
            vectors = self.deps.embedding_client.embed(chunks_text)
            chunk_orms: list[Chunk] = []
            chunk_vectors: list[ChunkVector] = []
            bm25_docs: list[BM25Doc] = []
            for i, ct in enumerate(chunks_text):
                token_count = self._token_counter.count(ct)
                # 写入PostgreSQL 结构化元数据:为了事务一致性和关系查询
                chunk = await self.deps.chunk_repo.create(
                    doc_id=doc_id,
                    content=ct,
                    chunk_index=i,
                    token_count=token_count,
                )
                chunk_orms.append(chunk)
                # 生成向量,并存入Milvus向量库
                chunk_vectors.append(
                    ChunkVector(chunk_id=chunk.id, doc_id=doc_id, embedding=vectors[i])
                )
                # 构建bm25索引文档
                bm25_docs.append(BM25Doc(chunk_id=chunk.id, content=ct, doc_id=doc_id))

            if chunk_vectors:
                self.deps.vector_store.upsert(chunk_vectors)
            if bm25_docs:
                # 将bm25索引文档写入应用程序内存中
                self.deps.bm25_store.add_batch(bm25_docs)

            # 5. 并发实体抽取(信号量限流), 抽取结果按 chunk 顺序对齐
            extract_sem = asyncio.Semaphore(_EXTRACT_CONCURRENCY)

            async def _extract_chunk(content: str) -> ExtractResult:
                """单块实体抽取: 同步 LLM 调用移入线程池, 信号量限制并发."""
                async with extract_sem:
                    return await asyncio.to_thread(self.deps.entity_extractor.extract, content)

            extracts = await asyncio.gather(*(_extract_chunk(c.content) for c in chunk_orms))

            # 5.1 顺序写库: 实体名称-ID映射依赖跨块累积顺序
            total_entities = 0
            total_relations = 0
            all_name_to_id: dict[str, int] = {}  # 实体名称-数据库ID映射
            for chunk, extract in zip(chunk_orms, extracts, strict=True):
                if extract.entities:
                    orm_ents = await self.deps.graph_store.upsert_entities(
                        doc_id, chunk.id, extract.entities
                    )
                    for e in orm_ents:
                        all_name_to_id[e.name] = e.id  # 建立名称-ID映射
                    total_entities += len(orm_ents)  # 统计计数
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

            # 7. 文档已变更, 失效全部检索缓存(Redis 不可用时降级 no-op, 不阻塞索引)
            await self._retrieval_cache.clear_prefix()

            duration_ms = (time.perf_counter() - start) * 1000
            return IndexResult(
                doc_id=doc_id,
                chunk_count=len(chunk_orms),  # 返回总分块数
                entity_count=total_entities,  # 总实体数
                relation_count=total_relations,  # 总关系数
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
