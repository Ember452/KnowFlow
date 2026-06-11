"""SSE 事件编码与流式封装单测."""

import asyncio
from typing import Any

import pytest

from knowflow.api.sse import SSEEvent, make_event, sse_stream


def test_sse_event_to_dict_str_data() -> None:
    """str data 原样保留."""
    d = SSEEvent(event="token", data="hello").to_dict()
    assert d["event"] == "token"
    assert d["data"] == "hello"
    assert "id" not in d


def test_sse_event_to_dict_json_data() -> None:
    """非 str data JSON 序列化."""
    d = SSEEvent(event="retrieval", data={"chunk_id": 1, "score": 0.9}).to_dict()
    assert '"chunk_id": 1' in d["data"]


def test_make_event_helper() -> None:
    """make_event 便利函数."""
    d = make_event("done", {"total": 3})
    assert d["event"] == "done"
    assert "total" in d["data"]


def test_sse_event_with_id_retry() -> None:
    """带 id/retry 的事件."""
    d = SSEEvent(event="token", data="x", id="1", retry=1000).to_dict()
    assert d["id"] == "1"
    assert d["retry"] == 1000


class _FakeRequest:
    """fake Request, is_disconnected 永远 False."""

    async def is_disconnected(self) -> bool:
        return False


async def _gen(events: list[Any]) -> Any:
    for e in events:
        yield e


@pytest.mark.asyncio
async def test_sse_stream_yields_events() -> None:
    """sse_stream 透传业务事件."""
    events = [make_event("token", "a"), make_event("done", {})]
    stream = sse_stream(_FakeRequest(), _gen(events), heartbeat_interval=10)
    out = []
    async for e in stream:
        out.append(e)
    assert len(out) == 2
    assert out[0]["event"] == "token"
    assert out[1]["event"] == "done"


@pytest.mark.asyncio
async def test_sse_stream_heartbeat_on_idle() -> None:
    """事件间隔超过 heartbeat_interval 时插入心跳."""

    async def slow_gen() -> Any:
        yield make_event("token", "a")
        await asyncio.sleep(0.2)  # 超过 0.05s 心跳
        yield make_event("done", {})

    stream = sse_stream(_FakeRequest(), slow_gen(), heartbeat_interval=0.05)
    events = []
    async for e in stream:
        events.append(e)
    # 至少有一个心跳
    assert any(e["event"] == "heartbeat" for e in events)
    assert events[0]["event"] == "token"
    assert events[-1]["event"] == "done"
