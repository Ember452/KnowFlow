"""TaskBroker 单测 - 基于 FakeRedisStream 验证 enqueue/consume/ack/DLQ/重试语义."""

import pytest

from knowflow.tasks.broker import TaskBroker
from tests.fakes import FakeRedisStream


@pytest.mark.asyncio
async def test_ensure_group_idempotent() -> None:
    """重复创建消费组不报错(BUSYGROUP 忽略)."""
    redis = FakeRedisStream()
    broker = TaskBroker(redis)
    await broker.ensure_group("s", "g")
    await broker.ensure_group("s", "g")  # 第二次应静默
    assert ("s", "g") in redis._groups


@pytest.mark.asyncio
async def test_enqueue_and_consume() -> None:
    """投递后消费组能取到消息, payload 正确解析."""
    redis = FakeRedisStream()
    broker = TaskBroker(redis)
    await broker.ensure_group("s", "g")
    msg_id = await broker.enqueue("s", {"task": "index", "doc_id": 1, "attempts": 0})
    msgs = await broker.consume("s", "g", "c1", count=10, block_ms=0)
    assert len(msgs) == 1
    assert msgs[0].id == msg_id
    assert msgs[0].payload == {"task": "index", "doc_id": 1, "attempts": 0}


@pytest.mark.asyncio
async def test_consume_empty() -> None:
    """无消息时返回空列表."""
    redis = FakeRedisStream()
    broker = TaskBroker(redis)
    await broker.ensure_group("s", "g")
    msgs = await broker.consume("s", "g", "c1", count=1, block_ms=0)
    assert msgs == []


@pytest.mark.asyncio
async def test_ack_removes_from_pending() -> None:
    """ack 后消息不再被消费."""
    redis = FakeRedisStream()
    broker = TaskBroker(redis)
    await broker.ensure_group("s", "g")
    await broker.enqueue("s", {"task": "index", "doc_id": 1, "attempts": 0})
    msgs = await broker.consume("s", "g", "c1", count=1, block_ms=0)
    n = await broker.ack("s", "g", msgs[0].id)
    assert n == 1
    # 再次消费无消息
    msgs2 = await broker.consume("s", "g", "c1", count=1, block_ms=0)
    assert msgs2 == []


@pytest.mark.asyncio
async def test_send_to_dlq() -> None:
    """DLQ 写入死信流, 含失败原因与原 msg_id."""
    redis = FakeRedisStream()
    broker = TaskBroker(redis)
    dlq_id = await broker.send_to_dlq("dlq", "msg-1", {"task": "index", "doc_id": 1}, "boom")
    assert dlq_id is not None
    assert len(redis._streams["dlq"]) == 1


@pytest.mark.asyncio
async def test_message_not_redelivered_before_ack() -> None:
    """未 ack 的消息不会被同组其他 consumer 重复消费(PEL 语义)."""
    redis = FakeRedisStream()
    broker = TaskBroker(redis)
    await broker.ensure_group("s", "g")
    await broker.enqueue("s", {"task": "index", "doc_id": 1, "attempts": 0})
    msgs = await broker.consume("s", "g", "c1", count=1, block_ms=0)
    assert len(msgs) == 1
    # 另一个 consumer 同组消费, 不应再取到(已在 PEL)
    msgs2 = await broker.consume("s", "g", "c2", count=1, block_ms=0)
    assert msgs2 == []
