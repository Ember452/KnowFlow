"""Agent 端点 - Multi-Agent 编排状态查询(P8/M7 实现).

GET /agents/runs/{run_id} 返回父子 run 记录与委派链(状态机可见性),
供"构造多子任务场景 → 触发委派 → 查看状态机"验收与演示.
"""

from fastapi import APIRouter, HTTPException

from knowflow.api.deps import DbDep
from knowflow.db.repositories.agent_repo import AgentRunRepo, TaskDelegationRepo
from knowflow.schemas.agent import AgentRunDetail, AgentRunInfo, TaskDelegationInfo

router = APIRouter(prefix="/agents", tags=["agent"])


@router.get("/runs/{run_id}", response_model=AgentRunDetail)
async def get_agent_run(run_id: int, db: DbDep) -> AgentRunDetail:
    """查询 Agent 运行状态: 父子 run 记录与委派链."""
    run_repo = AgentRunRepo(db)
    del_repo = TaskDelegationRepo(db)

    run = await run_repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Agent 运行不存在: run_id={run_id}")

    children = await run_repo.list_children(run_id)
    delegations = await del_repo.list_by_parent(run_id)
    return AgentRunDetail(
        run=AgentRunInfo.model_validate(run),
        children=[AgentRunInfo.model_validate(c) for c in children],
        delegations=[TaskDelegationInfo.model_validate(d) for d in delegations],
    )
