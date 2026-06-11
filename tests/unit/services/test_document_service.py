"""DocumentService 单测 - upload/dedup/list/delete/reindex, 用 SQLite + fake MinIO/broker."""

import pytest

from knowflow.core.config import get_settings
from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.services.document_service import DocumentService
from tests.fakes import FakeBroker, FakeMinio


def _service(session, minio=None, broker=None) -> DocumentService:
    return DocumentService(
        session=session,
        minio=minio or FakeMinio(),
        broker=broker or FakeBroker(),
    )


@pytest.mark.asyncio
async def test_upload_stores_and_enqueues(db_session) -> None:
    """上传: 存 MinIO + 入库 pending + 投递索引任务."""
    minio = FakeMinio()
    broker = FakeBroker()
    svc = _service(db_session, minio, broker)
    resp = await svc.upload("note.md", b"# title\nbody", "u1")
    assert resp.status == "pending"
    assert resp.duplicated is False
    assert len(minio.put_calls) == 1
    assert len(broker.enqueued) == 1
    assert broker.enqueued[0][1]["task"] == "index"
    assert broker.enqueued[0][1]["doc_id"] == resp.doc_id


@pytest.mark.asyncio
async def test_upload_dedup_returns_existing(db_session) -> None:
    """同内容二次上传命中秒传, 不再存储/入队."""
    svc = _service(db_session)
    first = await svc.upload("a.md", b"same", "u1")
    minio2 = FakeMinio()
    broker2 = FakeBroker()
    svc2 = _service(db_session, minio2, broker2)
    second = await svc2.upload("b.md", b"same", "u1")
    assert second.duplicated is True
    assert second.doc_id == first.doc_id
    assert len(minio2.put_calls) == 0
    assert len(broker2.enqueued) == 0


@pytest.mark.asyncio
async def test_upload_rejects_bad_type(db_session) -> None:
    """不支持的扩展名校验失败."""
    svc = _service(db_session)
    with pytest.raises(ValidationError):
        await svc.upload("x.exe", b"MZ", "u1")


@pytest.mark.asyncio
async def test_upload_rejects_oversize(db_session) -> None:
    """超大文件校验失败."""
    svc = _service(db_session)
    settings = get_settings()
    big = b"x" * (settings.upload_max_bytes + 1)
    with pytest.raises(ValidationError):
        await svc.upload("big.md", big, "u1")


@pytest.mark.asyncio
async def test_list_pagination(db_session) -> None:
    """list 返回分页 items 与 total."""
    svc = _service(db_session)
    for i in range(3):
        await svc.upload(f"f{i}.md", f"content{i}".encode(), "u1")
    items, total = await svc.list("u1", limit=2, offset=0)
    assert total == 3
    assert len(items) == 2


@pytest.mark.asyncio
async def test_delete_removes_document(db_session) -> None:
    """删除后 list 不再包含."""
    svc = _service(db_session)
    up = await svc.upload("d.md", b"x", "u1")
    resp = await svc.delete(up.doc_id)
    assert resp.deleted is True
    _items, total = await svc.list("u1")
    assert total == 0


@pytest.mark.asyncio
async def test_delete_not_found(db_session) -> None:
    """删除不存在抛 NotFoundError."""
    svc = _service(db_session)
    with pytest.raises(NotFoundError):
        await svc.delete(99999)


@pytest.mark.asyncio
async def test_reindex_resets_status_and_enqueues(db_session) -> None:
    """reindex 置 pending 并投递 reindex 任务."""
    broker = FakeBroker()
    svc = _service(db_session, broker=broker)
    up = await svc.upload("r.md", b"x", "u1")
    broker.enqueued.clear()
    resp = await svc.reindex(up.doc_id)
    assert resp.status == "pending"
    assert len(broker.enqueued) == 1
    assert broker.enqueued[0][1]["task"] == "reindex"
