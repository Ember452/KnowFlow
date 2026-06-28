"""Replayer 单测 - checkpoint 恢复 + 时间序事件重放(注入 InMemorySaver)."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.agents.checkpoint import CheckpointManager
from knowflow.db.repositories.agent_repo import AgentRunRepo
from knowflow.db.repositories.session_repo import SessionRepo
from knowflow.observability.collector import SpanCollector
from knowflow.observability.replay import Replayer
from knowflow.observability.span import SpanType
from knowflow.observability.store import TraceStore
from knowflow.observability.tracer import Tracer


async def _seed(session: AsyncSession) -> tuple[int, int]:
    """种子: 会话 + 主 run + span 树. 返回 (session_id, run_id)."""
    sess = await SessionRepo(session).create(user_id="u1")
    await session.commit()
    sid = int(sess.id)
    run = await AgentRunRepo(session).create(session_id=sid, agent_type="main")
    await session.commit()

    store = TraceStore(session)
    collector = SpanCollector(store)
    tracer = Tracer(collector, trace_id_factory=lambda: "tr-r")
    await tracer.start_trace(session_id=sid)
    span = await tracer.start_span(SpanType.RETRIEVAL, "hybrid", input={"query": "报销"})
    await tracer.end_span(span, {"chunks": 2})
    await tracer.end_trace()
    await collector.flush()
    return sid, int(run.id)


@pytest.mark.asyncio
async def test_replay_restores_state(db_session: AsyncSession) -> None:
    """replay 恢复 checkpoint 状态(经 CheckpointManager.save 落库)."""
    sid, run_id = await _seed(db_session)
    manager = CheckpointManager(saver=InMemorySaver())
    await manager.save({"query": "报销流程", "needs_delegation": False}, str(run_id))

    result = await Replayer(manager, TraceStore(db_session)).replay(sid)
    assert result["run_id"] == run_id
    assert result["checkpoint_id"] is not None
    assert result["state"]["query"] == "报销流程"
    assert result["state"]["needs_delegation"] is False
    # 时间序事件: root + retrieval
    assert [e["span_type"] for e in result["events"]] == ["root", "retrieval"]
    assert result["events"][1]["input"] == {"query": "报销"}


@pytest.mark.asyncio
async def test_replay_specific_checkpoint(db_session: AsyncSession) -> None:
    """指定 checkpoint_id 恢复对应版本状态."""
    sid, run_id = await _seed(db_session)
    manager = CheckpointManager(saver=InMemorySaver())
    ckpt1 = await manager.save({"query": "v1"}, str(run_id))
    await manager.save({"query": "v2"}, str(run_id))

    result = await Replayer(manager, TraceStore(db_session)).replay(sid, ckpt1)
    assert result["state"]["query"] == "v1"
    assert result["checkpoint_id"] == ckpt1


@pytest.mark.asyncio
async def test_replay_without_checkpoint_raises(db_session: AsyncSession) -> None:
    """主 run 无 checkpoint 时抛 ValueError."""
    sid, _ = await _seed(db_session)
    manager = CheckpointManager(saver=InMemorySaver())
    with pytest.raises(ValueError, match="无 checkpoint"):
        await Replayer(manager, TraceStore(db_session)).replay(sid)


@pytest.mark.asyncio
async def test_replay_without_main_run_raises(db_session: AsyncSession) -> None:
    """会话无主 run 时抛 ValueError."""
    sess = await SessionRepo(db_session).create(user_id="u1")
    await db_session.commit()
    manager = CheckpointManager(saver=InMemorySaver())
    with pytest.raises(ValueError, match="无主 Agent run"):
        await Replayer(manager, TraceStore(db_session)).replay(int(sess.id))
