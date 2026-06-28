"""Tracer 单测 - trace 生命周期/嵌套/上下文传播/收尾兜底."""

import asyncio

import pytest

from knowflow.observability.span import Span, SpanType
from knowflow.observability.tracer import Tracer, current_span, current_trace_id, span_elapsed_ms


class FakeCollector:
    """内存 collector: 记录接收的 Span."""

    def __init__(self) -> None:
        self.spans: list[Span] = []

    def add(self, span: Span) -> None:
        self.spans.append(span)


@pytest.fixture(autouse=True)
def _clean_context() -> None:
    """每个用例后清空 contextvars, 避免用例间串扰."""
    from knowflow.observability import tracer as tracer_mod

    yield
    tracer_mod._TRACE_ID.set(None)
    tracer_mod._SPAN_STACK.set([])


@pytest.mark.asyncio
async def test_start_trace_sets_context() -> None:
    """start_trace 设置 trace_id 与根 Span."""
    tracer = Tracer(trace_id_factory=lambda: "trace-1")
    trace_id = await tracer.start_trace(session_id=7)
    assert trace_id == "trace-1"
    assert current_trace_id() == "trace-1"
    root = current_span()
    assert root is not None and root.span_type == "root"


@pytest.mark.asyncio
async def test_nested_spans_parent_chain() -> None:
    """嵌套 span: 子 span 的 parent 指向栈顶."""
    tracer = Tracer(trace_id_factory=lambda: "trace-2")
    await tracer.start_trace()
    outer = await tracer.start_span(SpanType.RETRIEVAL, "hybrid_retrieve")
    inner = await tracer.start_span(SpanType.AGENT_DECISION, "plan")
    assert inner.parent is outer
    assert outer.parent is not None and outer.parent.span_type == "root"
    await tracer.end_span(inner, {"plan": []})
    assert current_span() is outer  # 出栈后回到外层
    await tracer.end_span(outer)
    assert current_span().span_type == "root"


@pytest.mark.asyncio
async def test_end_span_collects_with_output() -> None:
    """end_span 记录 output/ended_at 并交给 collector."""
    collector = FakeCollector()
    tracer = Tracer(collector, trace_id_factory=lambda: "trace-3")
    await tracer.start_trace()
    span = await tracer.start_span(SpanType.TOOL_CALL, "calculator", input={"expr": "1+1"})
    await tracer.end_span(span, {"result": 2})
    assert len(collector.spans) == 1  # 子已收集, 根未结束
    assert collector.spans[0].output == {"result": 2}
    assert collector.spans[0].ended_at is not None
    assert span_elapsed_ms(span) >= 0


@pytest.mark.asyncio
async def test_end_span_failed_marks_metadata() -> None:
    """failed=True 时 metadata 标注失败."""
    collector = FakeCollector()
    tracer = Tracer(collector, trace_id_factory=lambda: "trace-4")
    await tracer.start_trace()
    span = await tracer.start_span(SpanType.TOOL_CALL, "file_read")
    await tracer.end_span(span, failed=True)
    assert collector.spans[0].metadata_ == {"failed": True}


@pytest.mark.asyncio
async def test_end_trace_forces_unfinished_spans() -> None:
    """end_trace 强制收尾未结束 span 并清空上下文."""
    collector = FakeCollector()
    tracer = Tracer(collector, trace_id_factory=lambda: "trace-5")
    await tracer.start_trace()
    await tracer.start_span(SpanType.MEMORY_RECALL, "recall")
    await tracer.end_trace()
    assert len(collector.spans) == 2  # 子 + 根全部收尾
    assert all(s.ended_at is not None for s in collector.spans)
    assert current_trace_id() is None
    assert current_span() is None


@pytest.mark.asyncio
async def test_no_collector_does_not_raise() -> None:
    """collector 为 None 时生命周期正常(可观测降级)."""
    tracer = Tracer(trace_id_factory=lambda: "trace-6")
    await tracer.start_trace()
    span = await tracer.start_span(SpanType.RETRIEVAL, "bm25")
    await tracer.end_span(span)
    await tracer.end_trace()
    assert span.ended_at is not None


@pytest.mark.asyncio
async def test_start_span_without_trace_auto_roots() -> None:
    """未 start_trace 直接 start_span 时自动补根."""
    tracer = Tracer(trace_id_factory=lambda: "trace-7")
    span = await tracer.start_span(SpanType.RETRIEVAL, "auto")
    assert span.trace_id == "trace-7"
    assert current_trace_id() == "trace-7"


@pytest.mark.asyncio
async def test_context_isolated_between_tasks() -> None:
    """子任务修改自己的 trace 上下文不影响父任务(任务级隔离)."""
    tracer = Tracer(trace_id_factory=lambda: "trace-8")

    async def worker() -> str:
        # 子任务开启自己的 trace(其 context 是父任务的副本)
        await tracer.start_trace()
        tid = current_trace_id() or "none"
        await tracer.end_trace()
        return tid

    await tracer.start_trace()
    task = asyncio.create_task(worker())
    assert current_trace_id() == "trace-8"  # 父任务不受子任务影响
    assert await task == "trace-8"
    assert current_trace_id() == "trace-8"  # 子任务结束后父上下文仍完好
