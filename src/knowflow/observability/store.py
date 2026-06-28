"""TraceStore - Span 批量落库与查询.

落库: 按 started_at 排序保证父先入(父 span 必先于子开始), 落库后解析父 id.
查询: 按 session 返回嵌套树(端点展示用) / 按 trace_id 时间序列表(replay 用).
聚合: 对话数/耗时分布/工具成功率/Trace 数(dashboard 用).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.db.repositories.trace_repo import TraceEventRepo, TraceSpanRepo
from knowflow.models.tool import ToolCall
from knowflow.models.trace import TraceEvent, TraceSpan
from knowflow.observability.span import Span

# 树节点结构: {span: TraceSpan, children: [...]}
SpanNode = dict[str, Any]


class TraceStore:
    """Trace 存储门面. 封装 TraceSpanRepo/TraceEventRepo, 提供批量与聚合."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._span_repo = TraceSpanRepo(session)
        self._event_repo = TraceEventRepo(session)

    # ── 写入 ──

    async def batch_insert(self, spans: list[Span]) -> int:
        """批量写入 Span, 返回写入条数.

        父先子后: 按 started_at 排序插入, 用内存 parent 引用解析 parent_span_id.
        """
        if not spans:
            return 0
        id_map: dict[int, int] = {}  # id(spn) -> 落库后的 span id
        for spn in sorted(spans, key=lambda s: (s.started_at, s.name)):
            parent_id = id_map[id(spn.parent)] if spn.parent is not None else None
            row = await self._span_repo.create(
                trace_id=spn.trace_id,
                span_type=spn.span_type,
                name=spn.name,
                session_id=spn.session_id,
                parent_span_id=parent_id,
                input=spn.input,
                output=spn.output,
                metadata=spn.metadata_,
            )
            # 透传内存态精确起止时间(替代 DB server_default)
            row.started_at = spn.started_at
            if spn.ended_at is not None:
                row.ended_at = spn.ended_at
            id_map[id(spn)] = int(row.id)
        await self.session.commit()
        return len(spans)

    # ── 查询 ──

    async def list_by_session(self, session_id: int) -> Sequence[TraceSpan]:
        """按会话列出全部 Span(时间升序)."""
        return await self._span_repo.list_by_session(session_id)

    async def tree_by_session(self, session_id: int) -> list[SpanNode]:
        """按会话构建嵌套树(端点展示用).

        根节点为 span_type="root"; 孤立 Span(父缺失)挂到根下.
        """
        spans = await self._span_repo.list_by_session(session_id)
        by_id: dict[int, SpanNode] = {}
        for spn in spans:
            by_id[int(spn.id)] = {"span": spn, "children": []}
        roots: list[SpanNode] = []
        for spn in spans:
            node = by_id[int(spn.id)]
            if spn.parent_span_id is not None and spn.parent_span_id in by_id:
                by_id[spn.parent_span_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    async def list_by_trace(self, trace_id: str) -> Sequence[TraceSpan]:
        """按 trace_id 列出全部 Span(时间升序, replay 用)."""
        return await self._span_repo.list_by_trace(trace_id)

    async def list_events(self, span_id: int) -> Sequence[TraceEvent]:
        """列出 Span 下的事件(时间升序)."""
        return await self._event_repo.list_by_span(span_id)

    # ── 聚合(dashboard) ──

    async def stats(self, hours: int = 24) -> dict[str, Any]:
        """近 N 小时聚合: 对话数/平均耗时/工具成功率/Trace 数."""
        since = datetime.now(UTC) - timedelta(hours=hours)
        # 会话数 = root span 数
        root_count = await self.session.scalar(
            select(func.count())
            .select_from(TraceSpan)
            .where(TraceSpan.span_type == "root", TraceSpan.started_at >= since)
        )
        # 检索/工具/记忆 span 数与平均耗时(Python 层聚合, 兼容 SQLite/PG 方言)
        latency_stmt = select(TraceSpan.span_type, TraceSpan.started_at, TraceSpan.ended_at).where(
            TraceSpan.span_type.in_(["retrieval", "tool_call", "memory_recall"]),
            TraceSpan.ended_at.is_not(None),
            TraceSpan.started_at >= since,
        )
        latency_rows = (await self.session.execute(latency_stmt)).all()
        span_counts: dict[str, int] = {}
        latencies: dict[str, list[float]] = {}
        for span_type, started, ended in latency_rows:
            span_counts[span_type] = span_counts.get(span_type, 0) + 1
            latencies.setdefault(span_type, []).append((ended - started).total_seconds() * 1000)
        # 工具成功率(复用 tool_calls 表, 口径与工具治理指标一致)
        tool_total = await self.session.scalar(
            select(func.count()).select_from(ToolCall).where(ToolCall.created_at >= since)
        )
        tool_ok = await self.session.scalar(
            select(func.count())
            .select_from(ToolCall)
            .where(ToolCall.created_at >= since, ToolCall.success.is_(True))
        )
        total_calls = int(tool_total or 0)
        ok_calls = int(tool_ok or 0)
        return {
            "hours": hours,
            "dialogs": int(root_count or 0),
            "traces": int(root_count or 0),
            "span_counts": span_counts,
            "avg_latency_ms": {k: round(sum(v) / len(v), 2) for k, v in latencies.items() if v},
            "tool_calls": total_calls,
            "tool_success_rate": round(ok_calls / total_calls * 100, 2) if total_calls else 0.0,
        }
