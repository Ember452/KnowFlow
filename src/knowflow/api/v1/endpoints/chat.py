"""对话端点 - M3 仅占位, 主流程在 P5(M4) 实现.

POST /chat 同步对话 · POST /chat/stream SSE 流式.
"""

from fastapi import APIRouter, HTTPException

from knowflow.schemas.chat import ChatRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", status_code=501)
async def chat(req: ChatRequest) -> None:
    """同步对话. P5(M4) 接对话主流程(检索 → 组装 prompt → LLM 生成)."""
    raise HTTPException(status_code=501, detail="对话主流程在 P5(M4) 实现")


@router.post("/stream", status_code=501)
async def chat_stream(req: ChatRequest) -> None:
    """SSE 流式对话. P5(M4) 接 retrieval→token→done 事件流."""
    raise HTTPException(status_code=501, detail="SSE 流式对话在 P5(M4) 实现")
