"""Trace 与 Replay Schema.

M3 仅定义 Schema 与路由占位, 可观测在 P10(M8) 实现.
对齐 models/trace.py: TraceSpan(trace_id/parent_span_id/span_type/name/input/output).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class TraceSpanInfo(BaseModel):
    """Trace Span 信息."""

    id: int
    trace_id: str
    parent_span_id: int | None = None
    session_id: int
    span_type: str = Field(description="agent_decision/tool_call/retrieval/memory_recall")
    name: str
    started_at: datetime | None = None
    ended_at: datetime | None = None


class ReplayRequest(BaseModel):
    """会话 Replay 请求."""

    session_id: int
    checkpoint_id: int | None = Field(default=None, description="从指定 checkpoint 恢复")
