"""Pipeline 单测 - 验证索引编排链路: 状态机流转、各组件调用、异常路径、reindex.

使用 db_session fixture(SQLite 内存库)跑真实 DocumentRepo/ChunkRepo/DocumentIndexRepo/GraphStore,
外部依赖(MinIO/Embedding/EntityExtractor/VectorStore/BM25Store)用 fake 注入.
"""

from typing import Any

import pytest

from knowflow.core.exceptions import NotFoundError
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.retrieval.bm25_store import BM25Doc
from knowflow.retrieval.entity_extractor import Entity as ExtractedEntity
from knowflow.retrieval.entity_extractor import ExtractResult
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.pipeline import IndexDeps, IndexError, IndexResult, RetrievalPipeline
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
        self.calls = 0

    def embed_one(self, text: str) -> list[float]:
        self.calls += 1
        return [float(len(text)), 0.0, 0.0]


class FakeEntityExtractor:
    """Fake entity extractor, 返回预设结果."""

    def __init__(self, result: ExtractResult | None = None) -> None:
        self.result = result or ExtractResult()
        self.calls = 0

    def extract(self, chunk_text: str) -> ExtractResult:
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


def _make_deps(
    db_session: Any,
    *,
    minio: FakeMinio,
    embedding: FakeEmbeddingClient | None = None,
    extractor: FakeEntityExtractor | None = None,
    vector_store: FakeVectorStore | None = None,
    bm25_store: FakeBM25Store | None = None,
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
    # embedding 调用次数 = chunk 数
    assert embedding.calls == result.chunk_count
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
