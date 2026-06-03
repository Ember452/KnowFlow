"""AgentRunRepo / TaskDelegationRepo / CheckpointRepo 单测, 重点验证父子链路."""

from datetime import UTC, datetime

import pytest

from knowflow.db.repositories.agent_repo import (
    AgentRunRepo,
    CheckpointRepo,
    TaskDelegationRepo,
)
from knowflow.db.repositories.session_repo import SessionRepo


@pytest.mark.asyncio
async def test_agent_run_create_and_get(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    await db_session.commit()

    run = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    fetched = await run_repo.get(run.id)
    assert fetched is not None
    assert fetched.agent_type == "main"
    assert fetched.status == "running"


@pytest.mark.asyncio
async def test_agent_run_list_children(db_session) -> None:  # type: ignore[no-untyped-def]
    """list_children 返回 parent_run_id 匹配的子运行."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    sub1 = await run_repo.create(session_id=sess.id, agent_type="sub", parent_run_id=main.id)
    sub2 = await run_repo.create(session_id=sess.id, agent_type="sub", parent_run_id=main.id)
    await db_session.commit()

    children = await run_repo.list_children(main.id)
    assert {c.id for c in children} == {sub1.id, sub2.id}


@pytest.mark.asyncio
async def test_agent_run_mark_completed(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    run = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    ended = datetime(2026, 8, 5, 12, 0, 0, tzinfo=UTC)
    ok = await run_repo.mark_completed(run.id, "completed", completed_at=ended)
    assert ok is True
    fetched = await run_repo.get(run.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.completed_at == ended

    assert await run_repo.mark_completed(99999) is False


@pytest.mark.asyncio
async def test_task_delegation_create_and_list(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    del_repo = TaskDelegationRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    d1 = await del_repo.create(parent_run_id=main.id, task="T1")
    d2 = await del_repo.create(parent_run_id=main.id, task="T2")
    await db_session.commit()

    delegations = await del_repo.list_by_parent(main.id)
    assert {d.id for d in delegations} == {d1.id, d2.id}


@pytest.mark.asyncio
async def test_task_delegation_update_status(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    del_repo = TaskDelegationRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    delegation = await del_repo.create(parent_run_id=main.id, task="T1")
    await db_session.commit()

    ok = await del_repo.update_status(
        delegation.id, "completed", result={"answer": "ok"}, checkpoint_id="ckpt-1"
    )
    assert ok is True
    fetched = await del_repo.get(delegation.id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.result == {"answer": "ok"}
    assert fetched.checkpoint_id == "ckpt-1"

    assert await del_repo.update_status(99999, "completed") is False


@pytest.mark.asyncio
async def test_checkpoint_save_and_get(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    ckpt_repo = CheckpointRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    run = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    state = {"messages": ["hello"], "step": 1}
    ckpt = await ckpt_repo.save(checkpoint_id="ckpt-1", agent_run_id=run.id, state=state)
    await db_session.commit()

    fetched = await ckpt_repo.get("ckpt-1")
    assert fetched is not None
    assert fetched.id == ckpt.id
    assert fetched.state == state
    assert fetched.agent_run_id == run.id


@pytest.mark.asyncio
async def test_checkpoint_lineage_walks_up(db_session) -> None:  # type: ignore[no-untyped-def]
    """lineage 应从当前向根回溯, 顺序为 [child, parent, root]."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    ckpt_repo = CheckpointRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    run = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    await ckpt_repo.save(checkpoint_id="root", agent_run_id=run.id, state={"step": 0})
    await ckpt_repo.save(
        checkpoint_id="mid",
        agent_run_id=run.id,
        state={"step": 1},
        parent_checkpoint_id="root",
    )
    await ckpt_repo.save(
        checkpoint_id="leaf",
        agent_run_id=run.id,
        state={"step": 2},
        parent_checkpoint_id="mid",
    )
    await db_session.commit()

    lineage = await ckpt_repo.lineage("leaf")
    assert [c.id for c in lineage] == ["leaf", "mid", "root"]
    assert lineage[-1].parent_checkpoint_id is None


@pytest.mark.asyncio
async def test_checkpoint_lineage_handles_missing(db_session) -> None:  # type: ignore[no-untyped-def]
    """不存在的 checkpoint_id 返回空链路."""
    ckpt_repo = CheckpointRepo(db_session)
    assert await ckpt_repo.lineage("not-exists") == []


@pytest.mark.asyncio
async def test_checkpoint_lineage_single_node_no_parent(db_session) -> None:  # type: ignore[no-untyped-def]
    """根 checkpoint 的 lineage 只含自身, 不死循环."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    ckpt_repo = CheckpointRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    run = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    await ckpt_repo.save(checkpoint_id="root", agent_run_id=run.id, state={"step": 0})
    await db_session.commit()

    lineage = await ckpt_repo.lineage("root")
    assert len(lineage) == 1
    assert lineage[0].id == "root"
    assert lineage[0].parent_checkpoint_id is None
