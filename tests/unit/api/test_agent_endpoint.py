"""Agent 端点单测 - run 状态/父子/委派链查询(P8 实现)."""

from fastapi.testclient import TestClient

from knowflow.db.repositories.agent_repo import AgentRunRepo, TaskDelegationRepo
from knowflow.db.repositories.session_repo import SessionRepo


def test_agent_run_not_found(client: TestClient) -> None:
    """不存在的 run 返回 404."""
    resp = client.get("/api/v1/agents/runs/99999")
    assert resp.status_code == 404


def test_agent_run_detail_with_children_and_delegations(
    client: TestClient, api_session_factory: object
) -> None:
    """构造主/子 run + 委派记录, 查询详情可见父子链."""
    import asyncio

    async def seed() -> int:
        async with api_session_factory() as session:  # type: ignore[attr-defined]
            sess = await SessionRepo(session).create(user_id="u1")
            run_repo = AgentRunRepo(session)
            main = await run_repo.create(session_id=sess.id, agent_type="main")
            sub = await run_repo.create(session_id=sess.id, agent_type="sub", parent_run_id=main.id)
            del_repo = TaskDelegationRepo(session)
            await del_repo.create(
                parent_run_id=main.id, task="查 A 的价格", child_run_id=sub.id, status="completed"
            )
            await session.commit()
            return int(main.id)

    main_id = asyncio.run(seed())
    resp = client.get(f"/api/v1/agents/runs/{main_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["agent_type"] == "main"
    assert data["run"]["status"] == "running"
    assert len(data["children"]) == 1
    assert data["children"][0]["agent_type"] == "sub"
    assert len(data["delegations"]) == 1
    assert data["delegations"][0]["task"] == "查 A 的价格"
    assert data["delegations"][0]["child_run_id"] == data["children"][0]["id"]
