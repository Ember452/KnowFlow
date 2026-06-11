"""评测端点 - M3 仅占位, 离线评测与指标复现在 P10(M8) 实现."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run", status_code=501)
async def run_eval() -> None:
    """启动评测. P10(M8) 接 EvalRunner."""
    raise HTTPException(status_code=501, detail="离线评测与指标复现在 P10(M8) 实现")


@router.get("/runs/{run_id}", status_code=501)
async def get_eval_run(run_id: int) -> None:
    """查询评测结果. P10(M8) 实现."""
    raise HTTPException(status_code=501, detail="离线评测与指标复现在 P10(M8) 实现")
