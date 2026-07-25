"""DocumentService 单测 - upload/dedup/list/delete/reindex, 用 SQLite + fake MinIO/broker."""

from typing import Any

import pytest

from knowflow.core.config import get_settings
from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.services.document_service import DocumentService
from tests.fakes import FakeBroker, FakeMinio


def _service(session, minio=None, broker=None, retrieval_cache=None) -> DocumentService:
    return DocumentService(
        session=session,
        minio=minio or FakeMinio(),
        broker=broker or FakeBroker(),
        retrieval_cache=retrieval_cache,
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


class _BoomBroker(FakeBroker):
    """enqueue 抛异常的 broker, 模拟 Redis 短暂故障."""

    async def enqueue(self, stream: str, payload: dict[str, Any], **_: Any) -> str:
        raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_upload_rolls_back_when_enqueue_fails(db_session) -> None:
    """投递失败: 文档不落库 + MinIO 对象被清理, 异常向上抛, 同内容可重传."""
    minio = FakeMinio()
    svc = _service(db_session, minio, _BoomBroker())
    with pytest.raises(ConnectionError):
        await svc.upload("n.md", b"x", "u1")
    await db_session.rollback()  # 模拟 get_db 会话退出时的回滚
    _items, total = await svc.list("u1")
    assert total == 0
    assert minio.objects == {}
    assert minio.remove_calls  # 已清理 MinIO 对象


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
async def test_delete_clears_retrieval_cache(db_session) -> None:
    """删除成功后失效全部检索缓存(知识库已变更, 不得返回过期结果)."""

    class FakeRetrievalCache:
        def __init__(self) -> None:
            self.clear_calls = 0

        async def clear_prefix(self, prefix: str = "knowflow:retrieval:") -> None:
            self.clear_calls += 1

    cache = FakeRetrievalCache()
    svc = _service(db_session, retrieval_cache=cache)
    up = await svc.upload("d.md", b"x", "u1")
    await svc.delete(up.doc_id)
    assert cache.clear_calls == 1

    # 删除不存在的文档不触发失效
    cache.clear_calls = 0
    with pytest.raises(NotFoundError):
        await svc.delete(99999)
    assert cache.clear_calls == 0


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
