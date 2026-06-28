"""Span 数据模型 - 可观测最小单元.

对齐设计文档 3.4 模块六: 嵌套结构(parent 引用) + trace_id 贯穿请求.
span_id 由落库时 DB 分配(自增), 内存态用对象引用表达父子关系.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


class SpanType:
    """Span 类型常量(对齐 models/trace.py 注释)."""

    AGENT_DECISION = "agent_decision"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    MEMORY_RECALL = "memory_recall"


@dataclass
class Span:
    """单个观测 Span.

    Attributes:
        trace_id: 请求级 trace id, 贯穿整个调用链.
        span_type: agent_decision/tool_call/retrieval/memory_recall.
        name: Span 名称(如 "hybrid_retrieve" / "call_calculator").
        session_id: 关联会话(可空).
        parent: 父 Span 引用(None 为根). 落库时解析为 parent_span_id.
        input/output: 入参/出参快照(JSON 可序列化).
        started_at/ended_at: 起止时间(UTC).
        metadata_: 附加业务信息(如 run_id/checkpoint_id).
    """

    trace_id: str
    span_type: str
    name: str
    parent: Span | None = field(default=None, repr=False)
    session_id: int | None = None
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    metadata_: dict[str, Any] | None = None

    def end(self, output: dict[str, Any] | None = None) -> None:
        """结束 Span: 记录出参快照与结束时间."""
        self.output = output
        self.ended_at = datetime.now(UTC)
