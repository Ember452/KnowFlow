"""SSE 流式封装 - 事件编码 / 心跳 / 客户端断开检测.

事件类型(对齐 core/constants.py SSEEventType):
    token / tool_start / tool_end / retrieval / progress / done / error / heartbeat

与 sse-starlette 的 EventSourceResponse 配合: 提供 event dict 生成器.
chat/stream 在 P5(M4) 接对话主流程, 本模块提供底层工具.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from starlette.requests import Request

HEARTBEAT_INTERVAL_SECONDS = 15  # 心跳间隔, 防止代理超时断连

_SENTINEL = object()  # 生产者结束标记


@dataclass(frozen=True)
class SSEEvent:
    """SSE 事件. 转为 EventSourceResponse 接受的 dict."""

    event: str
    data: Any
    id: str | None = None
    retry: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """转为 sse-starlette EventSourceResponse 接受的 dict."""
        d: dict[str, Any] = {"event": self.event, "data": _encode_data(self.data)}
        if self.id is not None:
            d["id"] = self.id
        if self.retry is not None:
            d["retry"] = self.retry
        return d


def _encode_data(data: Any) -> str:
    """data 为 str 时原样返回, 否则 JSON 序列化."""
    if isinstance(data, str):
        return data
    return json.dumps(data, ensure_ascii=False, default=str)


def make_event(event: str, data: Any = None) -> dict[str, Any]:
    """便利函数: 构造单个 SSE 事件 dict."""
    return SSEEvent(event=event, data=data).to_dict()


async def sse_stream(
    request: Request,
    event_gen: AsyncIterator[dict[str, Any]],
    *,
    heartbeat_interval: int = HEARTBEAT_INTERVAL_SECONDS,
) -> AsyncIterator[dict[str, Any]]:
    """包装事件生成器, 注入心跳与断开检测.

    用独立生产者任务 + 队列解耦: 心跳超时不取消业务生成器在途的 await,
    避免 LLM 流式生成被心跳误杀.

    Args:
        request: HTTP 请求(用于检测客户端断开).
        event_gen: 业务事件生成器(yield dict).
        heartbeat_interval: 心跳间隔秒.

    Yields:
        sse-starlette 接受的事件 dict.
    """
    queue: asyncio.Queue[object] = asyncio.Queue()
    heartbeat = make_event("heartbeat", "")

    async def _producer() -> None:
        try:
            async for event in event_gen:
                await queue.put(event)
        except Exception as exc:
            queue.put_nowait(make_event("error", {"error": str(exc)}))
        finally:
            queue.put_nowait(_SENTINEL)

    task = asyncio.create_task(_producer())
    try:
        while True:
            if await request.is_disconnected():
                return
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except TimeoutError:
                yield heartbeat
                continue
            if item is _SENTINEL:
                return
            yield item  # type: ignore[misc]
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
