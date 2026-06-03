"""TraceSpanRepo / TraceEventRepo 单测."""

from datetime import UTC, datetime

import pytest

from knowflow.db.repositories.session_repo import SessionRepo
from knowflow.db.repositories.trace_repo import TraceEventRepo, TraceSpanRepo


@pytest.mark.asyncio
async def test_span_create_and_get(db_session) -> None:  # type: ignore[no-untyped-def]
    span_repo = TraceSpanRepo(db_session)
    span = await span_repo.create(
        trace_id="t1",
        span_type="agent_decision",
        name="decide",
        session_id=None,
    )
    await db_session.commit()

    fetched = await span_repo.get(span.id)
    assert fetched is not None
    assert fetched.trace_id == "t1"
    assert fetched.span_type == "agent_decision"
    assert fetched.ended_at is None


@pytest.mark.asyncio
async def test_span_list_by_trace_orders_by_started_at(db_session) -> None:  # type: ignore[no-untyped-def]
    span_repo = TraceSpanRepo(db_session)
    s1 = await span_repo.create(trace_id="t1", span_type="a", name="s1")
    s2 = await span_repo.create(trace_id="t1", span_type="b", name="s2")
    await span_repo.create(trace_id="t2", span_type="c", name="s3")
    await db_session.commit()

    spans = await span_repo.list_by_trace("t1")
    assert [s.id for s in spans] == [s1.id, s2.id]
    assert all(s.trace_id == "t1" for s in spans)


@pytest.mark.asyncio
async def test_span_list_by_session(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    span_repo = TraceSpanRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    await db_session.commit()

    await span_repo.create(trace_id="t1", span_type="a", name="s1", session_id=sess.id)
    await span_repo.create(trace_id="t2", span_type="b", name="s2", session_id=sess.id)
    await span_repo.create(trace_id="t3", span_type="c", name="s3")
    await db_session.commit()

    spans = await span_repo.list_by_session(sess.id)
    assert len(spans) == 2
    assert {s.trace_id for s in spans} == {"t1", "t2"}


@pytest.mark.asyncio
async def test_span_end_span(db_session) -> None:  # type: ignore[no-untyped-def]
    span_repo = TraceSpanRepo(db_session)
    span = await span_repo.create(trace_id="t1", span_type="tool_call", name="search")
    await db_session.commit()

    end_time = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)
    ok = await span_repo.end_span(span.id, output={"result": "ok"}, ended_at=end_time)
    assert ok is True
    fetched = await span_repo.get(span.id)
    assert fetched is not None
    assert fetched.output == {"result": "ok"}
    assert fetched.ended_at == end_time

    assert await span_repo.end_span(99999) is False


@pytest.mark.asyncio
async def test_span_metadata_round_trip(db_session) -> None:  # type: ignore[no-untyped-def]
    """metadata 字段(映射到列名 metadata)应能正常存取."""
    span_repo = TraceSpanRepo(db_session)
    span = await span_repo.create(
        trace_id="t1",
        span_type="retrieval",
        name="retrieve",
        metadata={"latency_ms": 120, "top_k": 5},
    )
    await db_session.commit()

    fetched = await span_repo.get(span.id)
    assert fetched is not None
    assert fetched.metadata_ == {"latency_ms": 120, "top_k": 5}


@pytest.mark.asyncio
async def test_event_create_and_list_by_span(db_session) -> None:  # type: ignore[no-untyped-def]
    span_repo = TraceSpanRepo(db_session)
    event_repo = TraceEventRepo(db_session)
    span = await span_repo.create(trace_id="t1", span_type="tool_call", name="search")
    await db_session.commit()

    e1 = await event_repo.create(span_id=span.id, event_type="token", data={"text": "hello"})
    e2 = await event_repo.create(span_id=span.id, event_type="token", data={"text": "world"})
    await db_session.commit()

    # list_by_span 应只返回当前 span 的事件(其他 span 的不返回)
    events = await event_repo.list_by_span(span.id)
    assert [e.id for e in events] == [e1.id, e2.id]
    assert events[0].data == {"text": "hello"}


@pytest.mark.asyncio
async def test_span_input_output_json_round_trip(db_session) -> None:  # type: ignore[no-untyped-def]
    """input/output(JSON)在 SQLite 上应能正常存取."""
    span_repo = TraceSpanRepo(db_session)
    span = await span_repo.create(
        trace_id="t1",
        span_type="tool_call",
        name="search",
        input={"query": "test"},
        output={"hits": [1, 2, 3]},
    )
    await db_session.commit()

    fetched = await span_repo.get(span.id)
    assert fetched is not None
    assert fetched.input == {"query": "test"}
    assert fetched.output == {"hits": [1, 2, 3]}
