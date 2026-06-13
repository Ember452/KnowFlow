"""worker 主进程单测 - 消费处理分支: 成功 ack / 重试入队 / DLQ / 异常兜底."""

from types import SimpleNamespace
from typing import Any

import pytest
from worker.main import _process
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
