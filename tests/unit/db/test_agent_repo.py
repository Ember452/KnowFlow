"""AgentRunRepo / TaskDelegationRepo 单测, 重点验证父子链路."""

from datetime import UTC, datetime

import pytest

from knowflow.db.repositories.agent_repo import AgentRunRepo, TaskDelegationRepo
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
