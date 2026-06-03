"""TraceSpan / TraceEvent 数据访问层."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.models.trace import TraceEvent, TraceSpan


class TraceSpanRepo:
    """Trace Span CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        trace_id: str,
        span_type: str,
        name: str,
        session_id: int | None = None,
        parent_span_id: int | None = None,
        input: dict | None = None,
        output: dict | None = None,
        metadata: dict | None = None,
    ) -> TraceSpan:
        """新建 Span. span_type: agent_decision/tool_call/retrieval/memory_recall."""
        span = TraceSpan(
            trace_id=trace_id,
            span_type=span_type,
            name=name,
            session_id=session_id,
            parent_span_id=parent_span_id,
            input=input,
            output=output,
            metadata_=metadata,
        )
        self.session.add(span)
        await self.session.flush()
        await self.session.refresh(span)
        return span

    async def get(self, span_id: int) -> TraceSpan | None:
        """按主键查 Span."""
        return await self.session.get(TraceSpan, span_id)

    async def list_by_trace(self, trace_id: str) -> Sequence[TraceSpan]:
        """按 trace_id 列出全部 Span, 按开始时间升序(replay 用)."""
        stmt = (
            select(TraceSpan)
            .where(TraceSpan.trace_id == trace_id)
            .order_by(TraceSpan.started_at.asc(), TraceSpan.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_session(self, session_id: int) -> Sequence[TraceSpan]:
        """按会话列出 Span."""
        stmt = (
            select(TraceSpan)
            .where(TraceSpan.session_id == session_id)
            .order_by(TraceSpan.started_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def end_span(
        self,
        span_id: int,
        output: dict | None = None,
        ended_at: datetime | None = None,
    ) -> bool:
        """结束 Span: 写入 output 与 ended_at. 返回是否命中.

        ended_at 缺省由调用方传入 datetime, 避免在 repo 层引入时区逻辑.
        """
        span = await self.get(span_id)
        if span is None:
            return False
        if output is not None:
            span.output = output
        if ended_at is not None:
            span.ended_at = ended_at
        await self.session.flush()
        return True


class TraceEventRepo:
    """Trace Event CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, span_id: int, event_type: str, data: dict | None = None
    ) -> TraceEvent:
        """新建事件."""
        event = TraceEvent(span_id=span_id, event_type=event_type, data=data)
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def list_by_span(self, span_id: int) -> Sequence[TraceEvent]:
        """按 Span 列出事件, 按时间升序."""
        stmt = (
            select(TraceEvent)
            .where(TraceEvent.span_id == span_id)
            .order_by(TraceEvent.created_at.asc(), TraceEvent.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
