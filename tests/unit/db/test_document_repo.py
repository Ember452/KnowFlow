"""DocumentRepo / ChunkRepo / DocumentIndexRepo 单测.

使用 SQLite+aiosqlite 内存库, 通过 conftest.py 的 db_session fixture 注入.
JSONBType 在 SQLite 自动降级为 JSON, LargeBinary 原生支持, 无需 PG.
"""

import pytest

from knowflow.db.repositories.document_repo import (
    ChunkRepo,
    DocumentIndexRepo,
    DocumentRepo,
)
from knowflow.models.document import Chunk


@pytest.mark.asyncio
async def test_document_create_and_get(db_session) -> None:  # type: ignore[no-untyped-def]
    """create 后应能通过 get 取回, 默认 status=pending."""
    repo = DocumentRepo(db_session)
    doc = await repo.create(
        title="测试文档",
        source_uri="docs/test.pdf",
        file_type="pdf",
        size_bytes=1024,
        user_id="u1",
    )
    await db_session.commit()

    fetched = await repo.get(doc.id)
    assert fetched is not None
    assert fetched.title == "测试文档"
    assert fetched.status == "pending"
    assert fetched.user_id == "u1"


@pytest.mark.asyncio
async def test_document_list_by_user_orders_desc(db_session) -> None:  # type: ignore[no-untyped-def]
    """list_by_user 应按 id 倒序返回."""
    repo = DocumentRepo(db_session)
    d1 = await repo.create(title="d1", source_uri="a", file_type="pdf", size_bytes=1, user_id="u1")
    d2 = await repo.create(title="d2", source_uri="b", file_type="pdf", size_bytes=1, user_id="u1")
    await db_session.commit()

    docs = await repo.list_by_user("u1")
    assert [d.id for d in docs] == [d2.id, d1.id]


@pytest.mark.asyncio
async def test_document_update_status(db_session) -> None:  # type: ignore[no-untyped-def]
    """update_status 应更新状态与错误信息, 未命中返回 False."""
    repo = DocumentRepo(db_session)
    doc = await repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    await db_session.commit()

    ok = await repo.update_status(doc.id, "ready")
    assert ok is True
    fetched = await repo.get(doc.id)
    assert fetched is not None
    assert fetched.status == "ready"

    ok = await repo.update_status(99999, "ready")
    assert ok is False


@pytest.mark.asyncio
async def test_document_find_by_content_hash(db_session) -> None:  # type: ignore[no-untyped-def]
    """按内容哈希查重."""
    repo = DocumentRepo(db_session)
    await repo.create(
        title="d",
        source_uri="a",
        file_type="pdf",
        size_bytes=1,
        content_hash="abc123",
    )
    await db_session.commit()

    found = await repo.find_by_content_hash("abc123")
    assert found is not None
    assert found.content_hash == "abc123"
    assert await repo.find_by_content_hash("not_exists") is None


@pytest.mark.asyncio
async def test_document_find_by_content_hash_scoped_to_user(db_session) -> None:  # type: ignore[no-untyped-def]
    """查重限定用户范围: 不同用户同 hash 不互相命中."""
    repo = DocumentRepo(db_session)
    await repo.create(
        title="d",
        source_uri="a",
        file_type="pdf",
        size_bytes=1,
        content_hash="abc123",
        user_id="u1",
    )
    await db_session.commit()

    assert await repo.find_by_content_hash("abc123", user_id="u1") is not None
    assert await repo.find_by_content_hash("abc123", user_id="u2") is None


@pytest.mark.asyncio
async def test_document_get_many_titles(db_session) -> None:  # type: ignore[no-untyped-def]
    """get_many_titles 批量返回 doc_id -> title, 空列表返回空 dict."""
    repo = DocumentRepo(db_session)
    d1 = await repo.create(title="报销手册", source_uri="a", file_type="pdf", size_bytes=1)
    d2 = await repo.create(title="考勤制度", source_uri="b", file_type="pdf", size_bytes=1)
    await db_session.commit()

    titles = await repo.get_many_titles([d1.id, d2.id])
    assert titles == {d1.id: "报销手册", d2.id: "考勤制度"}
    assert await repo.get_many_titles([]) == {}


@pytest.mark.asyncio
async def test_chunk_create_and_list_by_doc(db_session) -> None:  # type: ignore[no-untyped-def]
    """分块按 chunk_index 升序返回."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    await db_session.commit()

    await chunk_repo.create(doc_id=doc.id, content="第二段", chunk_index=1, token_count=10)
    await chunk_repo.create(doc_id=doc.id, content="第一段", chunk_index=0, token_count=10)
    await db_session.commit()

    chunks = await chunk_repo.list_by_doc(doc.id)
    assert [c.chunk_index for c in chunks] == [0, 1]
    assert chunks[0].content == "第一段"


@pytest.mark.asyncio
async def test_chunk_bulk_create(db_session) -> None:  # type: ignore[no-untyped-def]
    """bulk_create 应返回带 id 的对象."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    await db_session.commit()

    chunks = [Chunk(doc_id=doc.id, content=f"c{i}", chunk_index=i, token_count=1) for i in range(3)]
    created = await chunk_repo.bulk_create(chunks)
    await db_session.commit()

    assert all(c.id is not None for c in created)
    assert len(await chunk_repo.list_by_doc(doc.id)) == 3


@pytest.mark.asyncio
async def test_chunk_get_many_preserves_order(db_session) -> None:  # type: ignore[no-untyped-def]
    """get_many 应按输入顺序返回, 跳过不存在的 id."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    await db_session.commit()

    c1 = await chunk_repo.create(doc_id=doc.id, content="a", chunk_index=0, token_count=1)
    c2 = await chunk_repo.create(doc_id=doc.id, content="b", chunk_index=1, token_count=1)
    await db_session.commit()

    got = await chunk_repo.get_many([c2.id, c1.id, 99999])
    assert [c.id for c in got] == [c2.id, c1.id]


@pytest.mark.asyncio
async def test_chunk_get_many_empty_input(db_session) -> None:  # type: ignore[no-untyped-def]
    """空 id 列表应直接返回空, 不发 SQL."""
    chunk_repo = ChunkRepo(db_session)
    assert await chunk_repo.get_many([]) == []


@pytest.mark.asyncio
async def test_document_index_upsert_insert_then_update(db_session) -> None:  # type: ignore[no-untyped-def]
    """upsert 首次插入, 二次更新状态."""
    doc_repo = DocumentRepo(db_session)
    idx_repo = DocumentIndexRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    await db_session.commit()

    idx1 = await idx_repo.upsert(doc_id=doc.id, index_type="vector", status="pending")
    await db_session.commit()
    idx2 = await idx_repo.upsert(doc_id=doc.id, index_type="vector", status="ready")
    await db_session.commit()

    assert idx1.id == idx2.id
    assert idx2.status == "ready"
    items = await idx_repo.list_by_doc(doc.id)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_document_delete_cascades_chunks(db_session) -> None:  # type: ignore[no-untyped-def]
    """删除文档应级联删除分块(conftest 已开启 SQLite PRAGMA foreign_keys=ON)."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    await db_session.commit()

    ok = await doc_repo.delete(doc.id)
    await db_session.commit()
    assert ok is True
    assert await doc_repo.get(doc.id) is None
    assert await chunk_repo.list_by_doc(doc.id) == []
