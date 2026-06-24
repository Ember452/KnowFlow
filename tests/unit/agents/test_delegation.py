"""TaskDelegation 状态机单测 - 合法/非法转换与落库."""

import pytest

from knowflow.agents.delegation import TaskDelegationFactory
from knowflow.db.repositories.agent_repo import AgentRunRepo, TaskDelegationRepo
from knowflow.db.repositories.session_repo import SessionRepo


@pytest.mark.asyncio
async def test_delegation_state_machine_full_cycle(db_session) -> None:  # type: ignore[no-untyped-def]
    """created → delegated → running → completed 全流程落库."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    del_repo = TaskDelegationRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    sub = await run_repo.create(session_id=sess.id, agent_type="sub", parent_run_id=main.id)
    await db_session.commit()

    factory = TaskDelegationFactory(del_repo)
    delegation = await factory.create(parent_run_id=main.id, task="查 A 的价格")
    assert delegation.status == "created"

    await delegation.mark_delegated(int(sub.id))
    assert delegation.status == "delegated"
    await delegation.mark_running()
    assert delegation.status == "running"
    await delegation.complete({"output": "A 是 100"}, checkpoint_id="ckpt-1")
    assert delegation.status == "completed"

    await db_session.commit()
    fetched = await del_repo.get(delegation.delegation_id)
    assert fetched is not None
    assert fetched.status == "completed"
    assert fetched.child_run_id == sub.id
    assert fetched.result == {"output": "A 是 100"}
    assert fetched.checkpoint_id == "ckpt-1"


@pytest.mark.asyncio
async def test_delegation_fail_path(db_session) -> None:  # type: ignore[no-untyped-def]
    """running → failed 降级路径."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    del_repo = TaskDelegationRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    factory = TaskDelegationFactory(del_repo)
    delegation = await factory.create(parent_run_id=main.id, task="查 B")
    await delegation.mark_running()
    await delegation.fail("知识库未找到 B")
    assert delegation.status == "failed"
    await db_session.commit()

    fetched = await del_repo.get(delegation.delegation_id)
    assert fetched is not None
    assert fetched.status == "failed"
    assert fetched.result == {"error": "知识库未找到 B"}


@pytest.mark.asyncio
async def test_delegation_illegal_transition(db_session) -> None:  # type: ignore[no-untyped-def]
    """completed 后继续转换抛 ValueError."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    del_repo = TaskDelegationRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    factory = TaskDelegationFactory(del_repo)
    delegation = await factory.create(parent_run_id=main.id, task="T")
    await delegation.mark_running()
    await delegation.complete({"output": "ok"})
    with pytest.raises(ValueError, match="非法委派状态转换"):
        await delegation.fail("不该发生的失败")


@pytest.mark.asyncio
async def test_delegation_skip_delegated_is_allowed(db_session) -> None:  # type: ignore[no-untyped-def]
    """created 可直接 running(无 child_run_id 场景)."""
    sess_repo = SessionRepo(db_session)
    run_repo = AgentRunRepo(db_session)
    del_repo = TaskDelegationRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    main = await run_repo.create(session_id=sess.id, agent_type="main")
    await db_session.commit()

    factory = TaskDelegationFactory(del_repo)
    delegation = await factory.create(parent_run_id=main.id, task="T")
    await delegation.mark_running()
    assert delegation.status == "running"
