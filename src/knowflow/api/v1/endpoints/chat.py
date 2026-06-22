"""对话端点 - 同步对话与 SSE 流式对话.

POST /chat 同步返回完整答案与引用(含工具调用记录); POST /chat/stream 经 sse.py
心跳封装输出 retrieval → [tool_start/tool_end]* → token* → done 事件流,
异常时 error 事件. orchestrator 依赖不可用时自动回退直连检索链路;
记忆(短期观察/长期召回)与上下文策略在依赖齐备时启用.
"""

from typing import Any

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from knowflow.api.deps import (
    ContextManagerDep,
    DbDep,
    EmbeddingDep,
    LlmDep,
    OrchestratorDep,
    RedisDep,
    RetrieverDep,
)
from knowflow.api.sse import sse_stream
from knowflow.schemas.chat import ChatRequest, ChatResponse
from knowflow.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def _build_memory_manager(db: Any, redis: Any, llm: Any, embedding: Any) -> Any:
    """装配记忆管理器: 短期(Redis) + 重要性/压缩(LLM) + 长期(PG+向量)."""
    from knowflow.memory.compressor import Compressor
    from knowflow.memory.importance import ImportanceScorer
    from knowflow.memory.long_term import LongTermMemoryManager
    from knowflow.memory.manager import MemoryManager
    from knowflow.memory.short_term import ShortTermMemory

    return MemoryManager(
        short_term=ShortTermMemory(redis),
        importance=ImportanceScorer(llm),
        compressor=Compressor(llm),
        long_term=LongTermMemoryManager(db, embedding_client=embedding),
    )


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    db: DbDep,
    retriever: RetrieverDep,
    llm: LlmDep,
    orchestrator: OrchestratorDep,
    redis: RedisDep,
    embedding: EmbeddingDep,
    context_manager: ContextManagerDep,
) -> ChatResponse:
    """同步对话: 检索 → (工具编排/记忆/上下文策略) → LLM 生成 → 落库."""
    memory_manager = _build_memory_manager(db, redis, llm, embedding)
    service = ChatService(
        session=db,
        retriever=retriever,
        llm=llm,
        orchestrator=orchestrator,
        memory_manager=memory_manager,
        context_manager=context_manager,
    )
    return await service.chat(req)


@router.post("/stream")
async def chat_stream(
    request: Request,
    req: ChatRequest,
    db: DbDep,
    retriever: RetrieverDep,
    llm: LlmDep,
    orchestrator: OrchestratorDep,
    redis: RedisDep,
    embedding: EmbeddingDep,
    context_manager: ContextManagerDep,
) -> EventSourceResponse:
    """SSE 流式对话: retrieval → [tool_start/tool_end]* → token* → done 事件流(带心跳)."""
    memory_manager = _build_memory_manager(db, redis, llm, embedding)
    service = ChatService(
        session=db,
        retriever=retriever,
        llm=llm,
        orchestrator=orchestrator,
        memory_manager=memory_manager,
        context_manager=context_manager,
    )
    return EventSourceResponse(sse_stream(request, service.stream_events(req)))
