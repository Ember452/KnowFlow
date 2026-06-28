"""Tracer - Span 生命周期管理与上下文传播.

trace_id 经 contextvars 贯穿请求: 同一 async 任务链(含 asyncio.gather 子协程)
共享同一 trace_id 与嵌套栈, 子 Agent 并发执行天然挂在同一 trace 下.
collector 可注入(异步批量落库); None 时 Span 仅记录不落库(降级不阻塞主流程).
"""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from knowflow.core.logging import get_logger
from knowflow.observability.span import Span

logger = get_logger(__name__)

# 当前 trace_id 与 Span 嵌套栈(任务级隔离). 默认 None 避免可变默认值(list).
_TRACE_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
_SPAN_STACK: contextvars.ContextVar[list[Span] | None] = contextvars.ContextVar(
    "span_stack", default=None
)


def _stack() -> list[Span]:
    """取当前嵌套栈(未开启 trace 时为空栈)."""
    return _SPAN_STACK.get() or []


def current_trace_id() -> str | None:
    """当前上下文中的 trace_id(无 trace 时返回 None)."""
    return _TRACE_ID.get()


def current_span() -> Span | None:
    """当前上下文栈顶 Span(无嵌套时返回 None)."""
    stack = _stack()
    return stack[-1] if stack else None


class Tracer:
    """Span 生命周期门面: start_trace → start_span* → end_span* → end_trace.

    Args:
        collector: SpanCollector(实现 add(span)); None 时仅内存记录.
        trace_id_factory: trace_id 生成器(测试注入固定值).
    """

    def __init__(
        self,
        collector: Any | None = None,
        trace_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._collector = collector
        self._trace_id_factory = trace_id_factory or (lambda: str(uuid.uuid4()))

    async def start_trace(self, session_id: int | None = None) -> str:
        """开启新 trace: 生成 trace_id 并压入根 Span. 返回 trace_id."""
        trace_id = self._trace_id_factory()
        root = Span(trace_id=trace_id, span_type="root", name="root", session_id=session_id)
        _TRACE_ID.set(trace_id)
        _SPAN_STACK.set([root])
        logger.debug("tracer.trace_started", trace_id=trace_id, session_id=session_id)
        return trace_id

    async def start_span(
        self,
        span_type: str,
        name: str,
        *,
        input: dict[str, Any] | None = None,
        session_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Span:
        """开启子 Span, 挂到当前栈顶之下. 未开启 trace 时自动补根."""
        trace_id = _TRACE_ID.get()
        if trace_id is None:
            await self.start_trace(session_id)
            trace_id = _TRACE_ID.get()
            assert trace_id is not None  # start_trace 必定设置 trace_id
        stack = _stack()
        parent = stack[-1] if stack else None
        # 子 span 缺省继承父的 session_id(保证同一 trace 可整链按会话查询)
        if session_id is None and parent is not None:
            session_id = parent.session_id
        span = Span(
            trace_id=trace_id,
            span_type=span_type,
            name=name,
            parent=parent,
            session_id=session_id,
            input=input,
            metadata_=metadata,
        )
        _SPAN_STACK.set([*stack, span])
        logger.debug("tracer.span_started", trace_id=trace_id, name=name, type=span_type)
        return span

    async def end_span(
        self,
        span: Span,
        output: dict[str, Any] | None = None,
        *,
        failed: bool = False,
    ) -> None:
        """结束 Span: 出栈 + 记录出参/结束时间 + 交给 collector."""
        stack = _stack()
        if not stack or stack[-1] is not span:
            # 顺序异常(如并发交错)时按对象定位移除, 避免栈破坏
            logger.warning("tracer.span_end_order", name=span.name, trace_id=span.trace_id)
            stack = [s for s in stack if s is not span]
        else:
            stack = stack[:-1]
        _SPAN_STACK.set(stack)
        span.end(output)
        if failed:
            span.metadata_ = {**(span.metadata_ or {}), "failed": True}
        if self._collector is not None:
            self._collector.add(span)

    async def end_trace(self) -> None:
        """结束整个 trace: 栈内未结束的 Span 强制收尾, 清空上下文."""
        stack = _stack()
        for span in reversed(stack):
            if span.ended_at is None:
                span.end()
            if self._collector is not None:
                self._collector.add(span)
        _SPAN_STACK.set([])
        _TRACE_ID.set(None)
        logger.debug("tracer.trace_ended")


def span_elapsed_ms(span: Span) -> float:
    """Span 耗时(毫秒). 未结束时以当前时间计."""
    end = span.ended_at or datetime.now(UTC)
    return round((end - span.started_at).total_seconds() * 1000, 2)
