"""对话服务 - 检索增强问答主流程(支持工具调用增强).

链路: 会话存在性检查 → 消息入库 → 检索(retriever.retrieve) → 组装 prompt
(系统提示 + 最近 N 轮历史 + 检索上下文) → LLM 生成 → 消息/引用/轮次落库.

注入 orchestrator 后升级为工具版: 预检索结果同时注入检索上下文, 由
ToolOrchestrator 跑意图激活 → 可见工具注入 → 工具调用循环 → 最终答案,
工具调用记录随响应返回并落库; orchestrator 不可用/无可见工具时回退直连链路.

同步 chat() 返回完整响应; 流式 stream_events() 逐段 yield SSE 事件:
retrieval → [tool_start/tool_end]* → token* → done, 异常时 yield error 事件.
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
from knowflow.memory.manager import MemoryManager
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
        orchestrator: ToolOrchestrator(实现 async run)或 fake. None 时走直连检索链路.
        memory_manager: MemoryManager(观察/沉淀/召回)或 fake. None 时无记忆能力.
        context_manager: ContextManager(窗口/摘要/卸载/预算)或 fake. None 时用内置组装.
        multi_agent: MultiAgentOrchestrator(实现 async run)或 fake. None 时无多 Agent 编排.
    """

    def __init__(
        self,
        session: AsyncSession,
        retriever: Any,
        llm: Any | None = None,
        settings: Settings | None = None,
        orchestrator: Any | None = None,
        memory_manager: MemoryManager | None = None,
        context_manager: Any | None = None,
        multi_agent: Any | None = None,
    ) -> None:
        self.session = session
        self.retriever = retriever
        self._llm = llm
        self.settings = settings or get_settings()
        self._orchestrator = orchestrator
        self._memory_manager = memory_manager
        self._context_manager = context_manager
        self._multi_agent = multi_agent
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
    def _format_context(chunks: list[Any]) -> str:
        """检索片段格式化为上下文文本([n] 标注), 供 prompt 与工具编排器注入."""
        context_lines = [f"[{i + 1}] {c.content}" for i, c in enumerate(chunks)]
        return "\n\n".join(context_lines) if context_lines else "(无检索结果)"

    @staticmethod
    def _build_messages(
        query: str,
        history: list[dict[str, str]],
        chunks: list[Any],
        memory_text: str | None = None,
    ) -> list[dict[str, str]]:
        """组装 LLM 消息: 系统提示(含检索/记忆上下文) + 历史 + 当前问题."""
        context = ChatService._format_context(chunks)
        if memory_text:
            context += f"\n\n用户记忆:\n{memory_text}"
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
    def _citations_payload(
        citations: list[Citation], tool_calls: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """引用(与可选工具调用)序列化为消息 citations JSON 字段."""
        payload: dict[str, Any] = {"citations": [c.model_dump() for c in citations]}
        if tool_calls:
            payload["tool_calls"] = tool_calls
        return payload

    @staticmethod
    def _to_tool_calls_payload(tool_calls: list[Any]) -> list[dict[str, Any]]:
        """ToolCallRecord 列表 → 响应 payload(名称/参数/成败/耗时/错误)."""
        return [
            {
                "tool": tc.tool_name,
                "args": tc.args,
                "success": tc.success,
                "latency_ms": tc.latency_ms,
                "error": tc.error,
            }
            for tc in tool_calls
        ]

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

    # ── 记忆集成 ──

    async def _recall_memories(self, query: str, user_id: str | None) -> str:
        """召回用户长期记忆并格式化为提示文本; 无管理器/用户时返回空串."""
        if self._memory_manager is None or not user_id:
            return ""
        hits = await self._memory_manager.recall(
            query, user_id, top_k=self.settings.memory_recall_top_k
        )
        return self._memory_manager.recall_text(hits)

    async def _observe_and_sediment(
        self, session_id: int, user_id: str | None, role: str, content: str
    ) -> None:
        """消息写入短期记忆; assistant 落库后按轮次触发沉淀(与 db 事务同批提交)."""
        if self._memory_manager is None:
            return
        await self._memory_manager.observe(session_id, role, content)
        if role == "assistant":
            turns = len(await self._turns.list_by_session(session_id))
            if MemoryManager.should_sediment(turns, self._memory_manager.interval):
                await self._memory_manager.sediment(session_id, user_id or "anonymous")

    # ── 同步对话 ──

    async def chat(self, req: ChatRequest) -> ChatResponse:
        """同步对话: 检索 → (工具编排/记忆/上下文策略) → LLM 生成 → 落库."""
        start = time.perf_counter()
        session_id = await self._ensure_session(req.session_id, req.user_id)
        # 先取历史(当前消息入库前), 避免新消息重复注入
        history = await self._load_history(session_id, self.settings.window_max_turns)
        user_msg = await self._messages.create(
            session_id=session_id, role="user", content=req.message
        )
        await self._observe_and_sediment(session_id, req.user_id, "user", req.message)

        result = await self.retriever.retrieve(req.message, top_k=self.settings.retrieval_top_k)
        citations = self._to_citations(result.chunks)
        memory_text = await self._recall_memories(req.message, req.user_id)

        # Multi-Agent 版: 复杂任务(可拆分子任务)走编排(委派/并发/汇总), 否则回退下方链路
        if self._multi_agent is not None:
            try:
                ma = await self._multi_agent.run(
                    req.message,
                    session_id,
                    context=self._format_context(result.chunks),
                    history=history,
                )
            except Exception as exc:
                # 编排失败(如 checkpoint PG 不可用)不阻塞对话, 回退直连链路
                logger.warning("chat.multi_agent_failed_fallback", error=str(exc))
                ma = None
            if ma is not None and ma.intent == "complex" and ma.answer:
                return await self._finalize_chat(
                    session_id,
                    user_msg,
                    ma.answer,
                    citations,
                    [],
                    start,
                    user_id=req.user_id,
                )

        # 工具版: 预检索上下文注入编排器(含记忆), 工具调用后返回最终答案
        if self._orchestrator is not None:
            context = self._format_context(result.chunks)
            if memory_text:
                context += f"\n\n用户记忆:\n{memory_text}"
            orc = await self._orchestrator.run(
                req.message,
                session_id=str(session_id),
                history=history,
                context=context,
            )
            if not orc.no_tools:
                tool_calls = self._to_tool_calls_payload(orc.tool_calls)
                return await self._finalize_chat(
                    session_id,
                    user_msg,
                    orc.answer or "(无内容)",
                    citations,
                    tool_calls,
                    start,
                    user_id=req.user_id,
                )
            # 无可见工具: 回退直连链路

        messages = await self._build_context_messages(
            req.message, history, result.chunks, memory_text, session_id
        )
        llm = self._get_llm()
        response = await llm.ainvoke(messages)
        answer = self._extract_text(response)
        return await self._finalize_chat(
            session_id, user_msg, answer, citations, [], start, user_id=req.user_id
        )

    async def _build_context_messages(
        self,
        query: str,
        history: list[dict[str, str]],
        chunks: list[Any],
        memory_text: str,
        session_id: int,
    ) -> list[dict[str, str]]:
        """组装直连链路消息: 优先上下文管理器(窗口/摘要/预算), 否则内置组装."""
        if self._context_manager is not None:
            ctx = await self._context_manager.build(
                query,
                history,
                session_id=session_id,
                retrieval=self._format_context(chunks),
                memory=memory_text,
            )
            messages: list[dict[str, str]] = ctx.messages
            return messages
        return self._build_messages(query, history, chunks, memory_text)

    async def _finalize_chat(
        self,
        session_id: int,
        user_msg: Any,
        answer: str,
        citations: list[Citation],
        tool_calls: list[dict[str, Any]],
        start: float,
        *,
        user_id: str | None = None,
    ) -> ChatResponse:
        """同步链路收尾: 助手消息/轮次落库 + 记忆观察/沉淀 + 提交 + 响应构造."""
        tokens = self._count_tokens(answer)
        assistant_msg = await self._messages.create(
            session_id=session_id,
            role="assistant",
            content=answer,
            tokens=tokens,
            citations=self._citations_payload(citations, tool_calls),
        )
        await self._turns.create(
            session_id=session_id,
            user_message_id=int(user_msg.id),
            assistant_message_id=int(assistant_msg.id),
        )
        await self._observe_and_sediment(session_id, user_id, "assistant", answer)
        await self.session.commit()

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "chat.completed", session_id=session_id, tokens=tokens, latency_ms=round(latency_ms, 2)
        )
        return ChatResponse(
            session_id=str(session_id),
            answer=answer,
            citations=citations,
            tool_calls=tool_calls,
            latency_ms=round(latency_ms, 2),
        )

    # ── 流式对话(SSE) ──

    async def stream_events(self, req: ChatRequest) -> AsyncIterator[dict[str, Any]]:
        """SSE 事件流: retrieval → [tool_start/tool_end]* → token* → done; 异常时 error."""
        start = time.perf_counter()
        try:
            session_id = await self._ensure_session(req.session_id, req.user_id)
            history = await self._load_history(session_id, self.settings.window_max_turns)
            user_msg = await self._messages.create(
                session_id=session_id, role="user", content=req.message
            )
            await self._observe_and_sediment(session_id, req.user_id, "user", req.message)

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
            memory_text = await self._recall_memories(req.message, req.user_id)

            # Multi-Agent 版: 复杂任务走编排(委派/并发/汇总), 进度与结果以事件回传
            if self._multi_agent is not None:
                try:
                    ma = await self._multi_agent.run(
                        req.message,
                        session_id,
                        context=self._format_context(result.chunks),
                        history=history,
                    )
                except Exception as exc:
                    # 编排失败(如 checkpoint PG 不可用)不中断 SSE, 回退直连链路
                    logger.warning("chat.stream_multi_agent_failed_fallback", error=str(exc))
                    ma = None
                if ma is not None and ma.intent == "complex" and ma.answer:
                    yield make_event(
                        "progress",
                        {
                            "stage": "multi_agent",
                            "delegated": ma.delegated,
                            "subtasks": [s.id for s in ma.subtasks],
                            "run_id": ma.run_id,
                        },
                    )
                    yield make_event("token", {"delta": ma.answer})
                    async for event in self._finalize_stream(
                        session_id,
                        user_msg,
                        ma.answer,
                        citations,
                        [],
                        start,
                        user_id=req.user_id,
                    ):
                        yield event
                    return

            # 工具版: 先跑编排器(工具事件在 token 流之前), 无可见工具时回退直连链路
            if self._orchestrator is not None:
                context = self._format_context(result.chunks)
                if memory_text:
                    context += f"\n\n用户记忆:\n{memory_text}"
                orc = await self._orchestrator.run(
                    req.message,
                    session_id=str(session_id),
                    history=history,
                    context=context,
                )
                if not orc.no_tools:
                    for tc in orc.tool_calls:
                        yield make_event("tool_start", {"tool": tc.tool_name, "args": tc.args})
                        yield make_event(
                            "tool_end",
                            {
                                "tool": tc.tool_name,
                                "success": tc.success,
                                "latency_ms": tc.latency_ms,
                                "error": tc.error,
                            },
                        )
                    answer = orc.answer or "(无内容)"
                    tool_calls = self._to_tool_calls_payload(orc.tool_calls)
                    # 工具链路最终答案一次性以 token 事件回传, 保持事件序列兼容
                    yield make_event("token", {"delta": answer})
                    async for event in self._finalize_stream(
                        session_id,
                        user_msg,
                        answer,
                        citations,
                        tool_calls,
                        start,
                        user_id=req.user_id,
                    ):
                        yield event
                    return

            messages = await self._build_context_messages(
                req.message, history, result.chunks, memory_text, session_id
            )
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
            async for event in self._finalize_stream(
                session_id, user_msg, answer, citations, [], start, user_id=req.user_id
            ):
                yield event
        except Exception as exc:
            # 落库失败回滚, 不中断 SSE 流, 以 error 事件结束
            with contextlib.suppress(Exception):
                await self.session.rollback()
            logger.error("chat.stream_failed", error=str(exc))
            yield make_event("error", {"error": str(exc)})

    async def _finalize_stream(
        self,
        session_id: int,
        user_msg: Any,
        answer: str,
        citations: list[Citation],
        tool_calls: list[dict[str, Any]],
        start: float,
        *,
        user_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """流式链路收尾: 助手消息/轮次落库 + 记忆观察/沉淀 + 提交 + done 事件."""
        tokens = self._count_tokens(answer)
        assistant_msg = await self._messages.create(
            session_id=session_id,
            role="assistant",
            content=answer,
            tokens=tokens,
            citations=self._citations_payload(citations, tool_calls),
        )
        await self._turns.create(
            session_id=session_id,
            user_message_id=int(user_msg.id),
            assistant_message_id=int(assistant_msg.id),
        )
        await self._observe_and_sediment(session_id, user_id, "assistant", answer)
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
                "tool_calls": tool_calls,
                "latency_ms": round(latency_ms, 2),
                "tokens": tokens,
            },
        )
