"""对话端点 - 同步对话与 SSE 流式对话.

POST /chat 同步返回完整答案与引用(含工具调用记录); POST /chat/stream 经 sse.py
心跳封装输出 retrieval → [tool_start/tool_end]* → token* → done 事件流,
异常时 error 事件. orchestrator 依赖不可用时自动回退直连检索链路;
记忆(短期观察/长期召回)与上下文策略在依赖齐备时启用.
"""

from typing import Any

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse
from starlette.requests import Request

from knowflow.api.deps import (
    ContextManagerDep,
    DbDep,
    EmbeddingDep,
    LlmDep,
    MultiAgentDep,
    OrchestratorDep,
    RedisDep,
    RetrieverDep,
    UserDep,
)
from knowflow.api.sse import sse_stream
from knowflow.db.repositories.session_repo import MessageRepo, SessionRepo
from knowflow.retrieval.query_rewriter import QueryRewriter
from knowflow.schemas.chat import ChatRequest, ChatResponse
from knowflow.schemas.common import ApiResponse, PageResponse
from knowflow.schemas.session import MessageOut, SessionOut
from knowflow.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def _build_memory_manager(db: Any, redis: Any, llm: Any, embedding: Any) -> Any:
    """装配记忆管理器: 短期(Redis) + 重要性/压缩(LLM) + 长期(PG+向量).

    治理能力: 冲突检测留痕(ConflictStore 落 memory_conflicts 表),
    蒸馏摘要(压缩结果沉淀 memory_summaries 供召回注入).
    """
    from knowflow.memory.compressor import Compressor
    from knowflow.memory.conflict import ConflictStore
    from knowflow.memory.importance import ImportanceScorer
    from knowflow.memory.long_term import LongTermMemoryManager
    from knowflow.memory.manager import MemoryManager
    from knowflow.memory.short_term import ShortTermMemory

    return MemoryManager(
        short_term=ShortTermMemory(redis),
        importance=ImportanceScorer(llm),
        compressor=Compressor(llm),
        long_term=LongTermMemoryManager(db, embedding_client=embedding),
        conflict_store=ConflictStore(db),
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
    multi_agent: MultiAgentDep,
) -> ChatResponse:
    """同步对话: 检索 → (多 Agent 编排/工具编排/记忆/上下文策略) → LLM 生成 → 落库."""
    memory_manager = _build_memory_manager(db, redis, llm, embedding)
    service = ChatService(
        session=db,
        retriever=retriever,
        llm=llm,
        orchestrator=orchestrator,
        memory_manager=memory_manager,
        context_manager=context_manager,
        multi_agent=multi_agent,
        query_rewriter=QueryRewriter(llm),
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
    multi_agent: MultiAgentDep,
) -> EventSourceResponse:
    """SSE 流式对话: retrieval → [progress/tool_start/tool_end]* → token* → done 事件流(带心跳)."""
    memory_manager = _build_memory_manager(db, redis, llm, embedding)
    service = ChatService(
        session=db,
        retriever=retriever,
        llm=llm,
        orchestrator=orchestrator,
        memory_manager=memory_manager,
        context_manager=context_manager,
        multi_agent=multi_agent,
        query_rewriter=QueryRewriter(llm),
    )
    return EventSourceResponse(sse_stream(request, service.stream_events(req)))


@router.get("/sessions", response_model=ApiResponse[PageResponse[SessionOut]])
async def list_sessions(
    user_id: UserDep,
    db: DbDep,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ApiResponse[PageResponse[SessionOut]]:
    """列出当前用户的会话(按 id 倒序), 供前端历史侧边栏."""
    repo = SessionRepo(db)
    sessions = await repo.list_by_user(user_id, limit=limit, offset=offset)
    items = [
        SessionOut(
            id=s.id,
            user_id=s.user_id,
            title=s.title,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]
    return ApiResponse(data=PageResponse(items=items, total=len(items), limit=limit, offset=offset))


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse[list[MessageOut]])
async def list_messages(
    session_id: int,
    db: DbDep,
    limit: int = Query(default=200, ge=1, le=1000),
) -> ApiResponse[list[MessageOut]]:
    """列出会话的消息(按 id 升序/时间序), 供前端载入历史对话."""
    repo = MessageRepo(db)
    messages = await repo.list_by_session(session_id, limit=limit)
    items = [
        MessageOut(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            tokens=m.tokens,
            citations=m.citations,
            created_at=m.created_at,
        )
        for m in messages
    ]
    return ApiResponse(data=items)
