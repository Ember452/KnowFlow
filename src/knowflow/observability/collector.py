"""SpanCollector - 异步批量落库, 不阻塞主流程.

Span 先入内存缓冲, flush 时一次性批量写入(减少连接往返);
flush 由调用方显式触发(请求收尾)或后台定时任务兜底.
store 为 None 时仅缓冲不落库(降级, 对齐"可观测缺失不阻塞对话"原则).
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from knowflow.core.logging import get_logger
from knowflow.observability.span import Span

logger = get_logger(__name__)


class SpanCollector:
    """Span 收集器: add 缓冲 → flush 批量写 store.

    Args:
        store: TraceStore(实现 async batch_insert(spans)); None 时仅缓冲.
        flush_interval: 后台自动刷新间隔(秒); <=0 时禁用自动刷新.
    """

    def __init__(self, store: Any | None = None, flush_interval: float = 0.0) -> None:
        self._store = store
        self._pending: list[Span] = []
        self._task: asyncio.Task[None] | None = None
        self._flush_interval = flush_interval

    def add(self, span: Span) -> None:
        """收集一个已结束的 Span."""
        self._pending.append(span)

    async def flush(self) -> int:
        """批量写入全部缓冲 Span, 返回写入条数. 失败仅告警不抛出."""
        if not self._pending:
            return 0
        batch, self._pending = self._pending, []
        if self._store is None:
            return 0
        try:
            await self._store.batch_insert(batch)
            logger.debug("collector.flushed", count=len(batch))
            return len(batch)
        except Exception as exc:
            # 可观测写入失败不阻塞主流程: 丢弃本批并告警
            logger.warning("collector.flush_failed", count=len(batch), error=str(exc))
            return 0

    def start_auto_flush(self) -> None:
        """启动后台定时刷新任务(应用级单例调用一次)."""
        if self._flush_interval <= 0 or self._task is not None:
            return

        async def _loop() -> None:
            while True:
                await asyncio.sleep(self._flush_interval)
                await self.flush()

        self._task = asyncio.create_task(_loop())

    async def stop_auto_flush(self) -> None:
        """停止后台刷新并落掉残余缓冲(应用关闭时调用)."""
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self.flush()
