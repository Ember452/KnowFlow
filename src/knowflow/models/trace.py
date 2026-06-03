"""Trace 模型. TraceSpan / TraceEvent - 全链路可观测.

与设计文档 3.4 模块六一致, trace_spans 用 started_at/ended_at, trace_events 用 created_at.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, JSONBType


class TraceSpan(Base, IDMixin):
    """Trace Span. 嵌套结构, parent_span_id 记录父子, trace_id 贯穿请求."""

    __tablename__ = "trace_spans"

    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_span_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trace_spans.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    span_type: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="agent_decision/tool_call/retrieval/memory_recall"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    input: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONBType, nullable=True)

    __table_args__ = (
        Index("idx_trace_session", "session_id"),
        Index("idx_trace_id", "trace_id"),
    )


class TraceEvent(Base, IDMixin):
    """Trace 事件. Span 内的离散事件(如 token 输出节点)."""

    __tablename__ = "trace_events"

    span_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trace_spans.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_trace_events_span", "span_id"),)
