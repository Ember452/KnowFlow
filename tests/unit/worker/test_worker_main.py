"""worker 主进程单测 - 消费处理分支: 成功 ack / 重试入队 / DLQ / 异常兜底."""

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from worker.main import _consume_loop, _process
from worker.settings import WorkerSettings

from tests.fakes import FakeBroker


def _ws(max_retries: int = 3) -> WorkerSettings:
    return WorkerSettings(
        stream="s1",
        dlq_stream="dlq1",
        group="g1",
        consumer="c1",
        max_retries=max_retries,
        block_ms=100,
    )


def _msg(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(payload=payload, id="1-0")


class _BoomBroker(FakeBroker):
    """enqueue 抛异常的 broker, 模拟 Redis 故障."""

    async def enqueue(self, stream: str, payload: dict[str, Any], **_: Any) -> str:
        raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_init_deps_initializes_milvus(monkeypatch) -> None:
    """worker 启动必须初始化 Milvus(VectorStore 构造时取单例, 非懒加载)."""
    calls: list[str] = []

    async def fake_init_engine() -> None:
        calls.append("engine")

    async def fake_init_bm25(factory: Any) -> None:
        calls.append("bm25")

    def fake_session_factory() -> Any:
        return object()

    async def fake_init_redis() -> None:
        calls.append("redis")

    def fake_init_minio() -> None:
        calls.append("minio")

    def fake_init_milvus() -> Any:
        calls.append("milvus")
        return object()

    monkeypatch.setattr("knowflow.db.base.init_engine", fake_init_engine)
    monkeypatch.setattr("knowflow.db.base.get_session_factory", fake_session_factory)
    monkeypatch.setattr("knowflow.retrieval.bm25_store.init_bm25_store", fake_init_bm25)
    monkeypatch.setattr("knowflow.db.redis.init_redis", fake_init_redis)
    monkeypatch.setattr("knowflow.db.minio.init_minio", fake_init_minio)
    monkeypatch.setattr("knowflow.db.milvus.init_milvus", fake_init_milvus)

    from worker.main import _init_deps

    await _init_deps()
    assert "milvus" in calls
    assert calls.index("milvus") > calls.index("minio")


@pytest.mark.asyncio
async def test_process_ack_failure_keeps_consuming(monkeypatch) -> None:
    """任务成功但 ack 失败: 不抛异常(主循环不中断), 消息留 PEL."""

    async def fake_handle(payload: dict[str, Any], build_deps: Any) -> dict[str, Any]:
        return {"ok": True, "retryable": False, "doc_id": 1, "result": None}

    class _BoomAckBroker(FakeBroker):
        async def ack(self, stream: str, group: str, msg_id: str) -> int:
            raise ConnectionError("redis down")

    monkeypatch.setattr("worker.main.handle_index_task", fake_handle)
    broker = _BoomAckBroker()
    await _process(broker, _ws(), _msg({"task": "index", "doc_id": 1, "attempts": 0}))
    assert broker.acked == []
    assert broker.enqueued == []
    assert broker.dlq == []


@pytest.mark.asyncio
async def test_process_success_acks(monkeypatch) -> None:
    """任务成功: ack, 不重试不入 DLQ."""

    async def fake_handle(payload: dict[str, Any], build_deps: Any) -> dict[str, Any]:
        return {"ok": True, "retryable": False, "doc_id": 1, "result": None}

    monkeypatch.setattr("worker.main.handle_index_task", fake_handle)
    broker = FakeBroker()
    await _process(broker, _ws(), _msg({"task": "index", "doc_id": 1, "attempts": 0}))
    assert len(broker.acked) == 1
    assert broker.enqueued == []
    assert broker.dlq == []


@pytest.mark.asyncio
async def test_process_retryable_requeues(monkeypatch) -> None:
    """可重试且未超限: 重新入队(attempts+1)并 ack."""

    async def fake_handle(payload: dict[str, Any], build_deps: Any) -> dict[str, Any]:
        return {"ok": False, "retryable": True, "doc_id": 1, "result": None}

    monkeypatch.setattr("worker.main.handle_index_task", fake_handle)
    broker = FakeBroker()
    await _process(broker, _ws(max_retries=3), _msg({"task": "index", "doc_id": 1, "attempts": 0}))
    assert len(broker.enqueued) == 1
    assert broker.enqueued[0][1]["attempts"] == 1
    assert len(broker.acked) == 1
    assert broker.dlq == []


@pytest.mark.asyncio
async def test_process_retry_exhausted_goes_dlq(monkeypatch) -> None:
    """可重试但已超限: 入 DLQ 并 ack."""

    async def fake_handle(payload: dict[str, Any], build_deps: Any) -> dict[str, Any]:
        return {"ok": False, "retryable": True, "doc_id": 1, "result": None}

    monkeypatch.setattr("worker.main.handle_index_task", fake_handle)
    broker = FakeBroker()
    # attempts=2, max_retries=3 -> 2+1 < 3 不成立 -> DLQ
    await _process(broker, _ws(max_retries=3), _msg({"task": "index", "doc_id": 1, "attempts": 2}))
    assert len(broker.dlq) == 1
    assert len(broker.acked) == 1
    assert broker.enqueued == []


@pytest.mark.asyncio
async def test_process_requeue_failure_keeps_consuming(monkeypatch) -> None:
    """重试入队失败: 不抛异常(主循环不中断), 不 ack(消息留 PEL 供审计)."""

    async def fake_handle(payload: dict[str, Any], build_deps: Any) -> dict[str, Any]:
        return {"ok": False, "retryable": True, "doc_id": 1, "result": None}

    monkeypatch.setattr("worker.main.handle_index_task", fake_handle)
    broker = _BoomBroker()
    await _process(broker, _ws(max_retries=3), _msg({"task": "index", "doc_id": 1, "attempts": 0}))
    assert broker.acked == []
    assert broker.dlq == []


@pytest.mark.asyncio
async def test_process_unexpected_exception_retryable(monkeypatch) -> None:
    """任务抛非预期异常: 视为可重试, 重新入队."""

    async def fake_handle(payload: dict[str, Any], build_deps: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    monkeypatch.setattr("worker.main.handle_index_task", fake_handle)
    broker = FakeBroker()
    await _process(broker, _ws(max_retries=3), _msg({"task": "index", "doc_id": 1, "attempts": 0}))
    assert len(broker.enqueued) == 1
    assert broker.enqueued[0][1]["attempts"] == 1


class _FlakyBroker:
    """前两次 consume 抛 Redis 超时; 第三次恢复正常并请求停止."""

    def __init__(self, stop: asyncio.Event) -> None:
        self.attempts = 0
        self.stop = stop

    async def consume(self, *args: Any, **kwargs: Any) -> list[Any]:
        self.attempts += 1
        if self.attempts <= 2:
            raise TimeoutError("Timeout reading from 127.0.0.1:6379")
        self.stop.set()  # 恢复后立即请求停止, 保证循环在下次检查时退出
        return []

    async def ack(self, *args: Any, **kwargs: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_consume_loop_survives_redis_timeout(monkeypatch) -> None:
    """Redis 读取超时不崩溃: 退避重试后恢复消费, 进程保持存活."""
    monkeypatch.setattr("worker.main._RETRY_BASE_DELAY_S", 0.01)
    monkeypatch.setattr("worker.main._RETRY_MAX_DELAY_S", 0.02)

    stop = asyncio.Event()
    broker = _FlakyBroker(stop)
    await _consume_loop(broker, _ws(), stop)
    # 前两次超时被吞掉, 第三次正常消费后按 stop 退出
    assert broker.attempts == 3
