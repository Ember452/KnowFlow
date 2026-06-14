"""对话服务 - 检索增强问答主流程(无工具版先行).

链路: 会话存在性检查 → 消息入库 → 检索(retriever.retrieve) → 组装 prompt
(系统提示 + 最近 N 轮历史 + 检索上下文) → LLM 生成 → 消息/引用/轮次落库.

同步 chat() 返回完整响应; 流式 stream_events() 逐段 yield SSE 事件:
retrieval → token* → done, 异常时 yield error 事件.
P7 之前历史注入为"最近 window_max_turns 轮全量注入", 后续交给上下文工程替换.
"""

import contextlib
import time
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.api.sse import make_event
from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.core.llm import get_chat_llm
from knowflow.core.logging import get_logger
from knowflow.db.repositories.session_repo import MessageRepo, SessionRepo, TurnRepo
from knowflow.schemas.chat import ChatRequest, ChatResponse, Citation

logger = get_logger(__name__)

# 系统提示: 要求基于检索上下文作答并标注来源, 检索不到时如实说明
_SYSTEM_PROMPT_TEMPLATE = """你是 KnowFlow 企业知识库助手, 基于提供的知识片段回答问题.
要求:
1. 优先使用检索上下文回答, 不要编造事实
2. 引用来源时用 [n] 标注(对应检索片段序号)
3. 检索片段无法回答时, 如实说明"知识库中未找到相关信息"
4. 回答使用简洁的 Markdown 格式

检索上下文:
{context}"""


@lru_cache
def _get_tiktoken_encoding(model: str) -> Any | None:
    """按模型取 tiktoken 编码, 失败返回 None(调用方回退字符估算)."""
    try:
        import tiktoken

        return tiktoken.encoding_for_model(model)
    except Exception:
        return None


class ChatService:
    """对话服务. 每个请求构造一个实例, 持有当次依赖.

    Args:
        session: 请求级 AsyncSession(事务由服务管理).
        retriever: GraphRAGRetriever 或 fake(实现 async retrieve).
        llm: langchain BaseChatModel 或 fake(实现 ainvoke/astream). None 时懒加载单例.
        settings: Settings 单例.
    """

    def __init__(
        self,
        session: AsyncSession,
        retriever: Any,
        llm: Any | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.retriever = retriever
        self._llm = llm
        self.settings = settings or get_settings()
        self._sessions = SessionRepo(session)
        self._messages = MessageRepo(session)
        self._turns = TurnRepo(session)

    # ── 内部工具 ──

    def _get_llm(self) -> Any:
        """取 LLM: 优先注入实例, 否则懒加载全局单例."""
        return self._llm if self._llm is not None else get_chat_llm()

    async def _ensure_session(self, session_id: str | None, user_id: str | None) -> int:
        """校验/创建会话, 返回会话 id."""
        if session_id is not None:
            try:
                sid = int(session_id)
            except ValueError:
                raise ValidationError(f"非法 session_id: {session_id}") from None
            sess = await self._sessions.get(sid)
            if sess is None:
                raise NotFoundError(f"会话不存在: session_id={session_id}")
            return sid
        # 未传 session_id 时新建会话(标题留空, P7 可自动生成)
        sess = await self._sessions.create(user_id=user_id)
        return int(sess.id)

    async def _load_history(self, session_id: int, max_turns: int) -> list[dict[str, str]]:
        """取最近 max_turns 轮的 user/assistant 历史消息(不含刚入库的当前消息)."""
        messages = await self._messages.list_by_session(session_id, limit=max_turns * 4)
        history = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        # 每轮 2 条(user+assistant), 取最近 max_turns 轮
        return history[-(max_turns * 2) :]

    @staticmethod
    def _build_messages(
        query: str, history: list[dict[str, str]], chunks: list[Any]
    ) -> list[dict[str, str]]:
        """组装 LLM 消息: 系统提示(含检索上下文) + 历史 + 当前问题."""
        context_lines = [f"[{i + 1}] {c.content}" for i, c in enumerate(chunks)]
        context = "\n\n".join(context_lines) if context_lines else "(无检索结果)"
        system = _SYSTEM_PROMPT_TEMPLATE.replace("{context}", context)
        return [{"role": "system", "content": system}, *history, {"role": "user", "content": query}]

    @staticmethod
    def _to_citations(chunks: list[Any]) -> list[Citation]:
        """检索 chunk 转引用列表(content 截断防 JSON 膨胀)."""
        return [
            Citation(chunk_id=c.chunk_id, content=c.content[:500], score=c.score, source=c.source)
            for c in chunks
        ]

    @staticmethod
    def _citations_payload(citations: list[Citation]) -> dict[str, list[dict[str, Any]]]:
        """引用序列化为消息 citations JSON 字段."""
        return {"citations": [c.model_dump() for c in citations]}

    @staticmethod
    def _extract_text(obj: Any) -> str:
        """从 LLM 响应提取文本: 兼容 str 与 langchain 消息对象."""
        if isinstance(obj, str):
            return obj
        content = getattr(obj, "content", None)
        return str(content) if content is not None else ""

    def _count_tokens(self, text: str) -> int:
        """token 估算: tiktoken 精确计数, 失败回退字符/4 估算."""
        enc = _get_tiktoken_encoding(self.settings.llm_model)
        if enc is not None:
            return len(enc.encode(text))
        return len(text) // 4

    # ── 同步对话 ──

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """同步对话: 检索 → 组装 prompt → LLM 生成 → 消息/引用/轮次落库."""
        start = time.perf_counter()
        session_id = await self._ensure_session(req.session_id, req.user_id)
        # 先取历史(当前消息入库前), 避免新消息重复注入
        history = await self._load_history(session_id, self.settings.window_max_turns)
        user_msg = await self._messages.create(
            session_id=session_id, role="user", content=req.message
        )

        result = await self.retriever.retrieve(req.message, top_k=self.settings.retrieval_top_k)
        citations = self._to_citations(result.chunks)
        messages = self._build_messages(req.message, history, result.chunks)

        llm = self._get_llm()
        response = await llm.ainvoke(messages)
        answer = self._extract_text(response)

        tokens = self._count_tokens(answer)
        assistant_msg = await self._messages.create(
            session_id=session_id,
            role="assistant",
            content=answer,
            tokens=tokens,
            citations=self._citations_payload(citations),
        )
        await self._turns.create(
            session_id=session_id,
            user_message_id=int(user_msg.id),
            assistant_message_id=int(assistant_msg.id),
        )
        await self.session.commit()

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "chat.completed", session_id=session_id, tokens=tokens, latency_ms=round(latency_ms, 2)
        )
        return ChatResponse(
            session_id=str(session_id),
            answer=answer,
            citations=citations,
            latency_ms=round(latency_ms, 2),
        )

    # ── 流式对话(SSE) ──

    async def stream_events(self, req: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        """SSE 事件流: retrieval → token* → done; 异常时 yield error 事件."""
        start = time.perf_counter()
        try:
            session_id = await self._ensure_session(req.session_id, req.user_id)
            history = await self._load_history(session_id, self.settings.window_max_turns)
            user_msg = await self._messages.create(
                session_id=session_id, role="user", content=req.message
            )

            # 检索并先回传 retrieval 事件, 客户端可先行渲染引用
            result = await self.retriever.retrieve(req.message, top_k=self.settings.retrieval_top_k)
            citations = self._to_citations(result.chunks)
            yield make_event(
                "retrieval",
                {
                    "query": result.query,
                    "chunks": [
                        {
                            "chunk_id": c.chunk_id,
                            "content": c.content,
                            "score": c.score,
                            "source": c.source,
                        }
                        for c in result.chunks
                    ],
                    "latency_ms": result.latency_ms,
                },
            )

            messages = self._build_messages(req.message, history, result.chunks)
            llm = self._get_llm()
            # 逐 token 流式转发(JSON 载荷规避 SSE 分帧的换行边界问题)
            buffer: list[str] = []
            async for chunk in llm.astream(messages):
                token = self._extract_text(chunk)
                if not token:
                    continue
                buffer.append(token)
                yield make_event("token", {"delta": token})

            answer = "".join(buffer) or "(无内容)"
            tokens = self._count_tokens(answer)
            assistant_msg = await self._messages.create(
                session_id=session_id,
                role="assistant",
                content=answer,
                tokens=tokens,
                citations=self._citations_payload(citations),
            )
            await self._turns.create(
                session_id=session_id,
                user_message_id=int(user_msg.id),
                assistant_message_id=int(assistant_msg.id),
            )
            await self.session.commit()

            latency_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "chat.stream_completed",
                session_id=session_id,
                tokens=tokens,
                latency_ms=round(latency_ms, 2),
            )
            yield make_event(
                "done",
                {
                    "session_id": str(session_id),
                    "citations": [c.model_dump() for c in citations],
                    "latency_ms": round(latency_ms, 2),
                    "tokens": tokens,
                },
            )
        except Exception as exc:
            # 落库失败回滚, 不中断 SSE 流, 以 error 事件结束
            with contextlib.suppress(Exception):
                await self.session.rollback()
            logger.error("chat.stream_failed", error=str(exc))
            yield make_event("error", {"error": str(exc)})
