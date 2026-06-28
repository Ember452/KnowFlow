"""TraceStore 单测 - 批量落库/父子解析/树查询/聚合统计."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.db.repositories.session_repo import SessionRepo
from knowflow.models.tool import ToolCall
from knowflow.observability.collector import SpanCollector
from knowflow.observability.span import Span, SpanType
from knowflow.observability.store import TraceStore
from knowflow.observability.tracer import Tracer


async def _make_spans(session_id: int | None = None) -> list[Span]:
    """构造一个嵌套 trace: root → retrieval → tool_call."""
    root = Span(trace_id="tr-1", span_type="root", name="root", session_id=session_id)
    retrieval = Span(
        trace_id="tr-1",
        span_type=SpanType.RETRIEVAL,
        name="hybrid_retrieve",
        parent=root,
        session_id=session_id,
        input={"query": "报销流程"},
    )
    tool = Span(
        trace_id="tr-1",
        span_type=SpanType.TOOL_CALL,
        name="calculator",
        parent=retrieval,
        session_id=session_id,
    )
    # 列表输入顺序打乱, 验证 store 按 started_at 排序(父先子后, 均为过去时间保证正耗时)
    base = root.started_at
    root.started_at = base - timedelta(milliseconds=30)
    retrieval.started_at = base - timedelta(milliseconds=20)
    tool.started_at = base - timedelta(milliseconds=10)
    retrieval.end({"chunks": 3})
    tool.end({"result": 2})
    return [tool, root, retrieval]


@pytest.mark.asyncio
async def test_batch_insert_persists_parent_chain(db_session: AsyncSession) -> None:
    """批量落库: 父先子后, parent_span_id 正确解析."""
    sess = await SessionRepo(db_session).create(user_id="u1")
    await db_session.commit()
    sid = int(sess.id)
    store = TraceStore(db_session)
    spans = await _make_spans(session_id=sid)
    count = await store.batch_insert(spans)
    assert count == 3

    rows = await store.list_by_trace("tr-1")
    assert len(rows) == 3
    by_type = {r.span_type: r for r in rows}
    assert by_type["retrieval"].parent_span_id == by_type["root"].id
    assert by_type["tool_call"].parent_span_id == by_type["retrieval"].id
    assert by_type["retrieval"].input == {"query": "报销流程"}
    assert by_type["tool_call"].ended_at is not None


@pytest.mark.asyncio
async def test_tree_by_session_builds_nested(db_session: AsyncSession) -> None:
    """按会话查询返回嵌套树."""
    sess = await SessionRepo(db_session).create(user_id="u1")
    await db_session.commit()
    await TraceStore(db_session).batch_insert(await _make_spans(session_id=int(sess.id)))

    roots = await TraceStore(db_session).tree_by_session(int(sess.id))
    assert len(roots) == 1
    assert roots[0]["span"].span_type == "root"
    assert len(roots[0]["children"]) == 1  # retrieval
    assert len(roots[0]["children"][0]["children"]) == 1  # tool_call


@pytest.mark.asyncio
async def test_collector_flush_writes_batch(db_session: AsyncSession) -> None:
    """collector 缓冲后 flush 批量落库, 失败不抛出."""
    sess = await SessionRepo(db_session).create(user_id="u1")
    await db_session.commit()
    sid = int(sess.id)
    store = TraceStore(db_session)
    collector = SpanCollector(store)
    tracer = Tracer(collector, trace_id_factory=lambda: "tr-c")
    await tracer.start_trace(session_id=sid)
    span = await tracer.start_span(SpanType.RETRIEVAL, "bm25")
    await tracer.end_span(span)
    await tracer.end_trace()

    assert len(collector._pending) == 2
    written = await collector.flush()
    assert written == 2
    assert await store.list_by_trace("tr-c")  # 已落库


@pytest.mark.asyncio
async def test_collector_flush_failure_degrades(db_session: AsyncSession) -> None:
    """store 写入失败时 flush 告警不抛出, 主流程不受影响."""

    class BoomStore:
        async def batch_insert(self, spans: object) -> None:
            raise RuntimeError("PG 不可用")

    collector = SpanCollector(BoomStore())
    tracer = Tracer(collector, trace_id_factory=lambda: "tr-f")
    await tracer.start_trace()
    span = await tracer.start_span(SpanType.TOOL_CALL, "boom")
    await tracer.end_span(span)
    await tracer.end_trace()

    assert await collector.flush() == 0  # 降级: 丢弃本批


@pytest.mark.asyncio
async def test_stats_aggregates(db_session: AsyncSession) -> None:
    """stats 聚合: 对话数/span 数/工具成功率."""
    sess = await SessionRepo(db_session).create(user_id="u1")
    await db_session.commit()
    sid = int(sess.id)
    await TraceStore(db_session).batch_insert(await _make_spans(session_id=sid))

    # 一条成功工具调用 + 一条失败
    db_session.add(ToolCall(tool_name="calculator", success=True, latency_ms=10, token_usage=0))
    db_session.add(ToolCall(tool_name="search", success=False, latency_ms=5, token_usage=0))
    await db_session.commit()

    stats = await TraceStore(db_session).stats(hours=24)
    assert stats["dialogs"] == 1
    assert stats["traces"] == 1
    assert stats["span_counts"]["retrieval"] == 1
    assert stats["tool_calls"] == 2
    assert stats["tool_success_rate"] == 50.0
    assert stats["avg_latency_ms"]["retrieval"] >= 0


@pytest.mark.asyncio
async def test_collector_auto_flush_loop(db_session: AsyncSession) -> None:
    """后台自动刷新: 定时 flush 落库, stop 后残余缓冲落掉."""
    sess = await SessionRepo(db_session).create(user_id="u1")
    await db_session.commit()
    sid = int(sess.id)
    store = TraceStore(db_session)
    collector = SpanCollector(store, flush_interval=0.05)
    tracer = Tracer(collector, trace_id_factory=lambda: "tr-auto")

    collector.start_auto_flush()
    await tracer.start_trace(session_id=sid)
    span = await tracer.start_span(SpanType.RETRIEVAL, "auto_flush")
    await tracer.end_span(span)
    await tracer.end_trace()
    await asyncio.sleep(0.15)  # 等至少一个刷新周期
    assert await store.list_by_trace("tr-auto")  # 后台已落库

    await collector.stop_auto_flush()
    assert collector._task is None
    assert collector._pending == []  # 残余已落掉


@pytest.mark.asyncio
async def test_collector_disabled_auto_flush(db_session: AsyncSession) -> None:
    """flush_interval<=0 时不启动后台任务."""
    collector = SpanCollector(TraceStore(db_session), flush_interval=0.0)
    collector.start_auto_flush()
    assert collector._task is None
