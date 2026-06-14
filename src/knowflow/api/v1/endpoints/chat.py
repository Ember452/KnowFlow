"""对话端点 - 同步对话与 SSE 流式对话.

POST /chat 同步返回完整答案与引用; POST /chat/stream 经 sse.py 心跳封装
输出 retrieval → token* → done 事件流, 异常时 error 事件.
"""

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from knowflow.api.deps import DbDep, LlmDep, RetrieverDep
from knowflow.api.sse import sse_stream
from knowflow.schemas.chat import ChatRequest, ChatResponse
from knowflow.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, db: DbDep, retriever: RetrieverDep, llm: LlmDep) -> ChatResponse:
    """同步对话: 检索 → 组装 prompt → LLM 生成 → 落库, 返回答案与引用."""
    service = ChatService(session=db, retriever=retriever, llm=llm)
    return await service.chat(req)


@router.post("/stream")
async def chat_stream(
    request: Request,
    req: ChatRequest,
    db: DbDep,
    retriever: RetrieverDep,
    llm: LlmDep,
) -> EventSourceResponse:
    """SSE 流式对话: retrieval → token* → done 事件流(带心跳保活)."""
    service = ChatService(session=db, retriever=retriever, llm=llm)
    return EventSourceResponse(sse_stream(request, service.stream_events(req)))
