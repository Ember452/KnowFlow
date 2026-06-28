"""Trace 与 Replay Schema.

P10(M8) 实现: GET /traces/{session_id} 返回嵌套树, POST /traces/replay 重放,
GET /traces/stats 聚合统计(dashboard). 对齐 models/trace.py.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TraceSpanInfo(BaseModel):
    """Trace Span 信息."""

    id: int
    trace_id: str
    parent_span_id: int | None = None
    session_id: int | None = None
    span_type: str = Field(description="agent_decision/tool_call/retrieval/memory_recall")
    name: str
    input: dict | None = None
    output: dict | None = None
    metadata: dict | None = None
    started_at: datetime
    ended_at: datetime | None = None
    latency_ms: float | None = None


class TraceSpanNode(TraceSpanInfo):
    """嵌套树节点: 含子节点列表."""

    children: list[TraceSpanNode] = Field(default_factory=list)


class TraceTree(BaseModel):
    """会话 Trace 树."""

    session_id: int
    roots: list[TraceSpanNode]


class ReplayRequest(BaseModel):
    """会话 Replay 请求."""

    session_id: int
    checkpoint_id: str | None = Field(default=None, description="指定恢复点, 缺省取最新")


class ReplayEvent(BaseModel):
    """重放事件快照(按时间序)."""

    ts: str
    span_id: int
    parent_span_id: int | None = None
    span_type: str
    name: str
    input: dict | None = None
    output: dict | None = None
    ended_at: str | None = None


class ReplayResponse(BaseModel):
    """Replay 结果: 恢复状态 + 时间序事件."""

    session_id: int
    run_id: int
    checkpoint_id: str | None = None
    state: dict = Field(description="恢复的 AgentState")
    events: list[ReplayEvent]


class TraceStats(BaseModel):
    """聚合统计(dashboard 只读接口)."""

    hours: int
    dialogs: int
    traces: int
    span_counts: dict[str, int]
    avg_latency_ms: dict[str, float]
    tool_calls: int
    tool_success_rate: float
