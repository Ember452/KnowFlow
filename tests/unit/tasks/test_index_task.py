"""index_task 单测 - handle_index_task 调 pipeline 完成索引, 验证状态流转与异常分类.

patch get_session_factory 返回 SQLite factory; build_deps 注入 fake 组件 +
真实 repo. 复用 RetrievalPipeline 的索引链路.
"""

from collections.abc import Sequence
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.models import Base
from knowflow.retrieval.bm25_store import BM25Doc
from knowflow.retrieval.entity_extractor import ExtractResult
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.pipeline import IndexDeps
from knowflow.retrieval.vector_store import ChunkVector
from knowflow.tasks.index_task import handle_index_task


class _FakeMinio:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def fget_object(self, bucket: str, name: str, file_path: str) -> Any:
        with open(file_path, "wb") as f:
            f.write(self.content)
        return None


class _FakeEmbedding:
    def embed_one(self, text: str) -> list[float]:
        return [float(len(text)), 0.0]


class _FakeExtractor:
    def extract(self, chunk_text: str) -> ExtractResult:
        return ExtractResult()


class _FakeVectorStore:
    def upsert(self, chunks: Sequence[ChunkVector]) -> int:
        return len(chunks)

    def delete_by_doc(self, doc_id: int) -> int:
        return 0


class _FakeBM25Store:
    def add_batch(self, docs: Sequence[BM25Doc]) -> None:
        return None

    def delete_by_doc(self, doc_id: int) -> int:
        return 0


async def _make_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _fk(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _build_deps_factory(minio: _FakeMinio) -> Any:
    def _build(session: AsyncSession) -> IndexDeps:
        return IndexDeps(
            session=session,
            document_repo=DocumentRepo(session),
            chunk_repo=ChunkRepo(session),
            document_index_repo=DocumentIndexRepo(session),
            graph_store=GraphStore(session),
            vector_store=_FakeVectorStore(),
            bm25_store=_FakeBM25Store(),
            embedding_client=_FakeEmbedding(),
            entity_extractor=_FakeExtractor(),
            minio_client=minio,
            bucket="b",
        )

    return _build


@pytest.mark.asyncio
async def test_handle_index_task_success() -> None:
    """索引成功: 文档 pending → ready, 返回 ok."""
    factory = await _make_factory()
    # 预置文档
    async with factory() as session:
        repo = DocumentRepo(session)
        doc = await repo.create(
            title="t.md", source_uri="raw/t.md", file_type="md", size_bytes=10, status="pending"
        )
        await session.commit()
        doc_id = doc.id

    minio = _FakeMinio(b"# title\nsome content here")
    build_deps = _build_deps_factory(minio)

    with patch("knowflow.db.base.get_session_factory", return_value=factory):
        result = await handle_index_task(
            {"task": "index", "doc_id": doc_id, "attempts": 0}, build_deps
        )

    assert result["ok"] is True
    assert result["retryable"] is False
    assert result["result"].chunk_count >= 1

    # 验证状态已转 ready
    async with factory() as session:
        doc = await DocumentRepo(session).get(doc_id)
        assert doc is not None
        assert doc.status == "ready"


@pytest.mark.asyncio
async def test_handle_index_task_not_found_not_retryable() -> None:
    """文档不存在时返回不可重试(重试无意义)."""
    factory = await _make_factory()
    build_deps = _build_deps_factory(_FakeMinio(b""))
    with patch("knowflow.db.base.get_session_factory", return_value=factory):
        result = await handle_index_task(
            {"task": "index", "doc_id": 99999, "attempts": 0}, build_deps
        )
    assert result["ok"] is False
    assert result["retryable"] is False


@pytest.mark.asyncio
async def test_handle_index_task_missing_doc_id() -> None:
    """payload 缺 doc_id 返回不可重试."""
    build_deps = _build_deps_factory(_FakeMinio(b""))
    result = await handle_index_task({"task": "index"}, build_deps)
    assert result["ok"] is False
    assert result["retryable"] is False
    assert result["doc_id"] is None


@pytest.mark.asyncio
async def test_handle_index_task_failure_retryable() -> None:
    """MinIO 下载失败 → IndexError → 可重试."""
    factory = await _make_factory()
    async with factory() as session:
        repo = DocumentRepo(session)
        doc = await repo.create(
            title="t.md", source_uri="raw/t.md", file_type="md", size_bytes=10, status="pending"
        )
        await session.commit()
        doc_id = doc.id

    class _FailingMinio(_FakeMinio):
        def fget_object(self, bucket: str, name: str, file_path: str) -> Any:
            raise RuntimeError("minio down")

    build_deps = _build_deps_factory(_FailingMinio(b""))
    with patch("knowflow.db.base.get_session_factory", return_value=factory):
        result = await handle_index_task(
            {"task": "index", "doc_id": doc_id, "attempts": 0}, build_deps
        )
    assert result["ok"] is False
    assert result["retryable"] is True
