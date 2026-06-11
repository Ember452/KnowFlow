"""Agent 端点 - M3 仅占位, Multi-Agent 编排在 P8(M7) 实现."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/agents", tags=["agent"])


@router.get("/runs/{run_id}", status_code=501)
async def get_agent_run(run_id: int) -> None:
    """查询 Agent 运行状态. P8(M7) 接 LangGraph 编排与委派记录."""
    raise HTTPException(status_code=501, detail="Multi-Agent 编排在 P8(M7) 实现")
