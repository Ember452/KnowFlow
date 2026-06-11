"""Trace 端点 - M3 仅占位, 可观测与 Replay 在 P10(M8) 实现."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/traces", tags=["trace"])


@router.get("/{session_id}", status_code=501)
async def get_trace(session_id: int) -> None:
    """查询 Trace 树. P10(M8) 接 TraceSpan 存储与嵌套查询."""
    raise HTTPException(status_code=501, detail="可观测与 Replay 在 P10(M8) 实现")


@router.post("/replay", status_code=501)
async def replay() -> None:
    """会话 Replay. P10(M8) 接 checkpoint + trace 回放."""
    raise HTTPException(status_code=501, detail="可观测与 Replay 在 P10(M8) 实现")
