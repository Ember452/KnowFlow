"""Trace 端点 - Trace 树查询 / Replay / 聚合统计(P10/M8 实现).

GET  /traces/{session_id}        返回嵌套 span 树
GET  /traces/stats               近 N 小时聚合统计(dashboard 只读)
POST /traces/replay              按 checkpoint + trace 重放会话
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from knowflow.api.deps import DbDep
from knowflow.observability.replay import Replayer
from knowflow.observability.store import TraceStore
from knowflow.schemas.trace import (
    ReplayRequest,
    ReplayResponse,
    TraceSpanNode,
    TraceStats,
    TraceTree,
)

router = APIRouter(prefix="/traces", tags=["trace"])


def _to_node(spn: Any, children: list[TraceSpanNode]) -> TraceSpanNode:
    """ORM Span → 树节点(计算耗时毫秒)."""
    latency = None
    if spn.started_at is not None and spn.ended_at is not None:
        latency = round((spn.ended_at - spn.started_at).total_seconds() * 1000, 2)
    return TraceSpanNode(
        id=int(spn.id),
        trace_id=spn.trace_id,
        parent_span_id=int(spn.parent_span_id) if spn.parent_span_id else None,
        session_id=int(spn.session_id) if spn.session_id else None,
        span_type=spn.span_type,
        name=spn.name,
        input=spn.input,
        output=spn.output,
        metadata=spn.metadata_,
        started_at=spn.started_at,
        ended_at=spn.ended_at,
        latency_ms=latency,
        children=children,
    )


def _build_tree(roots: list[dict[str, Any]]) -> list[TraceSpanNode]:
    """store.tree_by_session 的节点结构 → schema 树."""
    return [_to_node(node["span"], _build_tree(node["children"])) for node in roots]


@router.get("/stats", response_model=TraceStats)
async def get_stats(db: DbDep, hours: int = 24) -> TraceStats:
    """近 N 小时聚合统计(对话数/耗时分布/工具成功率/Trace 数)."""
    stats = await TraceStore(db).stats(hours=hours)
    return TraceStats(**stats)


@router.get("/{session_id}", response_model=TraceTree)
async def get_trace(session_id: int, db: DbDep) -> TraceTree:
    """查询会话 Trace 树: root → retrieval/tool_call/memory_recall 嵌套结构."""
    roots = await TraceStore(db).tree_by_session(session_id)
    if not roots:
        raise HTTPException(status_code=404, detail=f"会话无 Trace 记录: session_id={session_id}")
    return TraceTree(session_id=session_id, roots=_build_tree(roots))


@router.post("/replay", response_model=ReplayResponse)
async def replay(req: ReplayRequest, db: DbDep) -> ReplayResponse:
    """按 checkpoint + trace 重放会话: 恢复 AgentState + 时间序事件流."""
    from knowflow.agents.checkpoint import CheckpointManager

    try:
        result = await Replayer(CheckpointManager(), TraceStore(db)).replay(
            req.session_id, req.checkpoint_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReplayResponse(**result)
