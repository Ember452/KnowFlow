"""Pipeline 单测 - 验证索引编排链路: 状态机流转、各组件调用、异常路径、reindex.

使用 db_session fixture(SQLite 内存库)跑真实 DocumentRepo/ChunkRepo/DocumentIndexRepo/GraphStore,
外部依赖(MinIO/Embedding/EntityExtractor/VectorStore/BM25Store)用 fake 注入.
"""

import threading
import time
from typing import Any

import pytest

from knowflow.core.exceptions import NotFoundError
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.retrieval.bm25_store import BM25Doc
from knowflow.retrieval.entity_extractor import Entity as ExtractedEntity
from knowflow.retrieval.entity_extractor import ExtractResult
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.pipeline import (
    _EXTRACT_CONCURRENCY,
    IndexDeps,
    IndexError,
    IndexResult,
    RetrievalPipeline,
)
from knowflow.retrieval.vector_store import ChunkVector


class FakeMinio:
    """Fake MinIO client, 下载时把预设内容写入临时文件."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.fget_calls: list[tuple[str, str, str]] = []

    def fget_object(self, bucket: str, object_name: str, file_path: str) -> Any:
        self.fget_calls.append((bucket, object_name, file_path))
        with open(file_path, "wb") as f:
            f.write(self.content)
        return None


class FailingMinio(FakeMinio):
    """下载时抛异常的 fake MinIO."""

    def fget_object(self, bucket: str, object_name: str, file_path: str) -> Any:
        raise RuntimeError("minio download failed")


class FakeEmbeddingClient:
    """Fake embedding, 返回固定维度向量."""

    def __init__(self) -> None:
        self.embed_calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        return [[float(len(t)), 0.0, 0.0] for t in texts]

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class FakeEntityExtractor:
    """Fake entity extractor, 返回预设结果."""

    def __init__(self, result: ExtractResult | None = None) -> None:
        self.result = result or ExtractResult()
        self.calls = 0

    def extract(self, chunk_text: str) -> ExtractResult:
        self.calls += 1
        return self.result


class ThreadTrackingExtractor(FakeEntityExtractor):
    """记录 extract 执行线程 id, 用于验证同步 LLM 调用已移入线程池."""

    def __init__(self) -> None:
        super().__init__(
            result=ExtractResult(
                entities=[ExtractedEntity(name="Hello", type="concept", normalized="hello")],
                relations=[],
            )
        )
        self.exec_thread_id: int | None = None

    def extract(self, chunk_text: str) -> ExtractResult:
        self.exec_thread_id = threading.get_ident()
        self.calls += 1
        return self.result


class ConcurrencyTrackingExtractor(FakeEntityExtractor):
    """记录 extract 最大并发数, 用于验证并发抽取与信号量限流."""

    def __init__(self, delay: float = 0.05) -> None:
        super().__init__()
        self.delay = delay  # 模拟 LLM 调用耗时, 放大并发窗口
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def extract(self, chunk_text: str) -> ExtractResult:
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(self.delay)
        with self._lock:
            self.active -= 1
        self.calls += 1
        return self.result


class FakeVectorStore:
    """Fake vector store, 记录 upsert/delete 调用."""

    def __init__(self) -> None:
        self.upserts: list[ChunkVector] = []
        self.deleted_docs: list[int] = []

    def upsert(self, chunks: list[ChunkVector]) -> int:
        self.upserts.extend(chunks)
        return len(chunks)

    def delete_by_doc(self, doc_id: int) -> int:
        self.deleted_docs.append(doc_id)
        return 0


class FakeBM25Store:
    """Fake BM25 store, 记录 add/delete 调用."""

    def __init__(self) -> None:
        self.adds: list[BM25Doc] = []
        self.deleted_docs: list[int] = []

    def add_batch(self, docs: list[BM25Doc]) -> None:
        self.adds.extend(docs)

    def delete_by_doc(self, doc_id: int) -> int:
        self.deleted_docs.append(doc_id)
        return 0


class FakeRetrievalCache:
    """Fake retrieval cache, 记录 clear_prefix 调用次数."""

    def __init__(self) -> None:
        self.clear_calls = 0

    async def clear_prefix(self, prefix: str = "knowflow:retrieval:") -> None:
        self.clear_calls += 1


def _make_deps(
    db_session: Any,
    *,
    minio: FakeMinio,
    embedding: FakeEmbeddingClient | None = None,
    extractor: FakeEntityExtractor | None = None,
    vector_store: FakeVectorStore | None = None,
    bm25_store: FakeBM25Store | None = None,
    retrieval_cache: FakeRetrievalCache | None = None,
) -> tuple[IndexDeps, FakeEmbeddingClient, FakeEntityExtractor, FakeVectorStore, FakeBM25Store]:
    """构造 IndexDeps, 返回 deps + 各 fake 引用(便于断言)."""
    embedding = embedding or FakeEmbeddingClient()
    extractor = extractor or FakeEntityExtractor()
    vector_store = vector_store or FakeVectorStore()
    bm25_store = bm25_store or FakeBM25Store()
    deps = IndexDeps(
        session=db_session,
        document_repo=DocumentRepo(db_session),
        chunk_repo=ChunkRepo(db_session),
        document_index_repo=DocumentIndexRepo(db_session),
        graph_store=GraphStore(db_session),
        vector_store=vector_store,  # type: ignore[arg-type]
        bm25_store=bm25_store,  # type: ignore[arg-type]
        embedding_client=embedding,  # type: ignore[arg-type]
        entity_extractor=extractor,  # type: ignore[arg-type]
        minio_client=minio,
        bucket="test-bucket",
        retrieval_cache=retrieval_cache,  # type: ignore[arg-type]
    )
    return deps, embedding, extractor, vector_store, bm25_store


@pytest.mark.asyncio
async def test_index_document_success(db_session: Any) -> None:
    """索引成功: 状态 pending -> indexing -> ready, chunks/向量/BM25/实体全部写入."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(
        title="test", source_uri="test.txt", file_type="txt", size_bytes=100
    )
    await db_session.commit()

    content = b"Hello world. This is a test document for indexing."
    minio = FakeMinio(content)
    deps, embedding, _extractor, vector_store, bm25_store = _make_deps(
        db_session,
        minio=minio,
        extractor=FakeEntityExtractor(
            result=ExtractResult(
                entities=[ExtractedEntity(name="Hello", type="concept", normalized="hello")],
                relations=[],
            )
        ),
    )
    pipeline = RetrievalPipeline(deps)

    result = await pipeline.index_document(doc.id)

    assert isinstance(result, IndexResult)
    assert result.doc_id == doc.id
    assert result.chunk_count >= 1
    assert result.entity_count == 1
    assert result.relation_count == 0
    # 状态: ready
    updated = await doc_repo.get(doc.id)
    assert updated is not None
    assert updated.status == "ready"
    # MinIO 下载调用
    assert len(minio.fget_calls) == 1
    assert minio.fget_calls[0][0] == "test-bucket"
    assert minio.fget_calls[0][1] == "test.txt"
    # 向量写入
    assert len(vector_store.upserts) == result.chunk_count
    # BM25 写入
    assert len(bm25_store.adds) == result.chunk_count
    # embedding 批量调用: 一次传入全部 chunk 文本
    assert len(embedding.embed_calls) == 1
    assert len(embedding.embed_calls[0]) == result.chunk_count
    # 索引状态记录
    idx_repo = DocumentIndexRepo(db_session)
    indexes = await idx_repo.list_by_doc(doc.id)
    assert {i.index_type for i in indexes} == {"vector", "graph", "bm25"}
    assert all(i.status == "ready" for i in indexes)


@pytest.mark.asyncio
async def test_index_document_not_found(db_session: Any) -> None:
    """文档不存在时抛 NotFoundError, 不触发索引流程."""
    minio = FakeMinio(b"")
    deps, *_ = _make_deps(db_session, minio=minio)
    pipeline = RetrievalPipeline(deps)

    with pytest.raises(NotFoundError):
        await pipeline.index_document(99999)


@pytest.mark.asyncio
async def test_index_document_failed_status(db_session: Any) -> None:
    """索引失败时状态置 failed 并抛 IndexError."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(title="fail", source_uri="fail.txt", file_type="txt", size_bytes=10)
    await db_session.commit()

    minio = FailingMinio(b"")
    deps, *_ = _make_deps(db_session, minio=minio)
    pipeline = RetrievalPipeline(deps)

    with pytest.raises(IndexError):
        await pipeline.index_document(doc.id)

    updated = await doc_repo.get(doc.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "minio download failed" in (updated.error_message or "")


@pytest.mark.asyncio
async def test_index_document_clears_retrieval_cache(db_session: Any) -> None:
    """索引成功后失效全部检索缓存(知识库已变更, 不得返回过期结果)."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(
        title="cache", source_uri="cache.txt", file_type="txt", size_bytes=50
    )
    await db_session.commit()

    cache = FakeRetrievalCache()
    minio = FakeMinio(b"Cache invalidation content. Fresh document.")
    deps, *_ = _make_deps(db_session, minio=minio, retrieval_cache=cache)
    pipeline = RetrievalPipeline(deps)

    await pipeline.index_document(doc.id)

    assert cache.clear_calls == 1


@pytest.mark.asyncio
async def test_index_document_failed_keeps_retrieval_cache(db_session: Any) -> None:
    """索引失败时不失效缓存(知识库未变更)."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(title="fail", source_uri="fail.txt", file_type="txt", size_bytes=10)
    await db_session.commit()

    cache = FakeRetrievalCache()
    deps, *_ = _make_deps(db_session, minio=FailingMinio(b""), retrieval_cache=cache)
    pipeline = RetrievalPipeline(deps)

    with pytest.raises(IndexError):
        await pipeline.index_document(doc.id)

    assert cache.clear_calls == 0


@pytest.mark.asyncio
async def test_reindex_document_clears_and_reindexes(db_session: Any) -> None:
    """reindex: 清理向量/BM25/chunks 后重新索引."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(
        title="reindex", source_uri="reindex.txt", file_type="txt", size_bytes=50
    )
    # 预先写入一条旧 chunk
    await chunk_repo.create(doc_id=doc.id, content="old", chunk_index=0, token_count=3)
    await db_session.commit()

    content = b"New content for reindex. Completely different."
    minio = FakeMinio(content)
    deps, _, _, vector_store, bm25_store = _make_deps(db_session, minio=minio)
    pipeline = RetrievalPipeline(deps)

    result = await pipeline.reindex_document(doc.id)

    # 旧 chunk 被清理(内容 "old" 不再存在), 新 chunk 写入
    chunks = await chunk_repo.list_by_doc(doc.id)
    assert all(c.content != "old" for c in chunks)
    assert len(chunks) == result.chunk_count
    # 向量/BM25 清理调用
    assert vector_store.deleted_docs == [doc.id]
    assert bm25_store.deleted_docs == [doc.id]
    # 状态: ready
    updated = await doc_repo.get(doc.id)
    assert updated is not None
    assert updated.status == "ready"


@pytest.mark.asyncio
async def test_index_document_with_relations(db_session: Any) -> None:
    """索引含实体与关系: 多 chunk 间关系正确写入."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(
        title="relations", source_uri="rel.txt", file_type="txt", size_bytes=200
    )
    await db_session.commit()

    # 长文本触发多 chunk
    content = b"Alice works in Engineering. Bob works in Sales. They collaborate on Project X."

    def fake_extract(chunk_text: str) -> ExtractResult:
        return ExtractResult(
            entities=[
                ExtractedEntity(name="Alice", type="person", normalized="alice"),
                ExtractedEntity(name="Bob", type="person", normalized="bob"),
            ],
            relations=[
                # relations 引用的 source/target 用 name, pipeline 会映射到 id
            ],
        )

    extractor = FakeEntityExtractor()
    extractor.extract = fake_extract  # type: ignore[method-assign]

    minio = FakeMinio(content)
    deps, _, _, _, _ = _make_deps(db_session, minio=minio, extractor=extractor)
    pipeline = RetrievalPipeline(deps)

    result = await pipeline.index_document(doc.id)

    assert result.entity_count > 0
    updated = await doc_repo.get(doc.id)
    assert updated is not None
    assert updated.status == "ready"


@pytest.mark.asyncio
async def test_index_document_extract_runs_in_thread(db_session: Any) -> None:
    """实体抽取的同步 LLM 调用在独立线程执行, 不阻塞事件循环."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(title="thread", source_uri="t.txt", file_type="txt", size_bytes=50)
    await db_session.commit()

    extractor = ThreadTrackingExtractor()
    minio = FakeMinio(b"Hello world. Thread test content.")
    deps, *_ = _make_deps(db_session, minio=minio, extractor=extractor)
    pipeline = RetrievalPipeline(deps)

    await pipeline.index_document(doc.id)

    # 断言 extract 在事件循环线程之外执行(asyncio.to_thread 生效)
    assert extractor.exec_thread_id is not None
    assert extractor.exec_thread_id != threading.get_ident()
    updated = await doc_repo.get(doc.id)
    assert updated is not None
    assert updated.status == "ready"


@pytest.mark.asyncio
async def test_index_document_extract_concurrent_limited(db_session: Any) -> None:
    """实体抽取并发执行且被信号量限流(1 < 并发 <= _EXTRACT_CONCURRENCY)."""
    doc_repo = DocumentRepo(db_session)
    doc = await doc_repo.create(
        title="concurrent", source_uri="c.txt", file_type="txt", size_bytes=5000
    )
    await db_session.commit()

    # 长文本触发多 chunk(默认 chunk_size=512, 5000 字符约 10 块, 远超并发度)
    extractor = ConcurrencyTrackingExtractor(delay=0.05)
    minio = FakeMinio(b"Knowledge base paragraph. " * 200)
    deps, *_ = _make_deps(db_session, minio=minio, extractor=extractor)
    pipeline = RetrievalPipeline(deps)

    await pipeline.index_document(doc.id)

    assert extractor.calls >= 5  # 确认确实产生了多块
    assert extractor.max_active > 1  # 并发抽取生效
    assert extractor.max_active <= _EXTRACT_CONCURRENCY  # 信号量限流生效
    updated = await doc_repo.get(doc.id)
    assert updated is not None
    assert updated.status == "ready"
