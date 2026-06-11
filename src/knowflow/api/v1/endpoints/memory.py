"""记忆端点 - M3 仅占位, 上下文工程与记忆在 P7(M6) 实现."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/{user_id}", status_code=501)
async def list_memory(user_id: str) -> None:
    """查询长期记忆. P7(M6) 接 LongTermMemory 存储."""
    raise HTTPException(status_code=501, detail="上下文工程与记忆在 P7(M6) 实现")


@router.delete("/{user_id}/{memory_id}", status_code=501)
async def delete_memory(user_id: str, memory_id: int) -> None:
    """删除记忆. P7(M6) 实现."""
    raise HTTPException(status_code=501, detail="上下文工程与记忆在 P7(M6) 实现")
