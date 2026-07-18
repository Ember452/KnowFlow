"""对话服务单测 - 会话创建/复用、消息落库、检索接线、流式事件序列与异常兜底."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.db.repositories.session_repo import MessageRepo, TurnRepo
from knowflow.schemas.chat import ChatRequest
from knowflow.services.chat_service import ChatService
from knowflow.services.tool_orchestrator import ToolCallRecord
from tests.fakes import (
    FakeChatLLM,
    FakeChunkWithScore,
    FakeMemoryManager,
    FakeMultiAgentOrchestrator,
    FakeRetriever,
    FakeToolOrchestrator,
)

_CHUNK = FakeChunkWithScore(
    chunk_id=1, content="报销流程: 填写报销单并提交部门审批。", score=0.9, source="hybrid"
)


def _service(
    session: AsyncSession,
    llm: FakeChatLLM | None = None,
    orchestrator: FakeToolOrchestrator | None = None,
    multi_agent: FakeMultiAgentOrchestrator | None = None,
) -> ChatService:
    return ChatService(
        session=session,
        retriever=FakeRetriever(chunks=[_CHUNK]),
        llm=llm or FakeChatLLM(),
        orchestrator=orchestrator,
        multi_agent=multi_agent,
    )


async def test_chat_creates_session_and_persists(db_session: AsyncSession) -> None:
    """同步对话: 新建会话 → 消息/引用/轮次全部落库."""
    llm = FakeChatLLM()
    resp = await _service(db_session, llm).chat(
        ChatRequest(message="报销流程是什么?", user_id="u1")
    )

    assert resp.answer == llm.answer
    assert len(resp.citations) == 1
    assert resp.citations[0].chunk_id == 1
    assert resp.session_id.isdigit()

    messages = await MessageRepo(db_session).list_by_session(int(resp.session_id))
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].content == llm.answer
    assert messages[1].citations["citations"][0]["chunk_id"] == 1

    turns = await TurnRepo(db_session).list_by_session(int(resp.session_id))
    assert len(turns) == 1


async def test_chat_reuses_session_with_history(db_session: AsyncSession) -> None:
    """多轮对话: 复用 session_id 时历史注入最近轮次."""
    llm = FakeChatLLM()
    service = _service(db_session, llm)
    first = await service.chat(ChatRequest(message="第一问", user_id="u1"))
    second = await service.chat(ChatRequest(message="第二问", session_id=first.session_id))

    assert second.session_id == first.session_id
    roles = [m["role"] for m in llm.last_messages]
    contents = [m["content"] for m in llm.last_messages]
    # 历史含上一轮的 user+assistant, 且当前问题在末尾
    assert roles[:2] == ["system", "user"]
    assert "第一问" in contents
    assert llm.answer in contents
    assert llm.last_messages[-1] == {"role": "user", "content": "第二问"}


class FakeQueryRewriter:
    """fake query 改写器: 记录调用, 返回预设结果."""

    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[tuple[str, list[dict[str, str]]]] = []

    async def rewrite(self, query: str, history: list[dict[str, str]]) -> str:
        self.calls.append((query, history))
        return self.result


class _BoomQueryRewriter:
    """改写抛异常的 fake, 验证回退原 query."""

    async def rewrite(self, query: str, history: list[dict[str, str]]) -> str:
        raise RuntimeError("rewrite failed")


async def test_chat_uses_rewritten_query_for_retrieval(db_session: AsyncSession) -> None:
    """多轮对话: 检索使用改写后的 query, 用户消息保持原文, 改写仅在有多轮历史时触发."""
    rewriter = FakeQueryRewriter(result="报销流程的具体步骤(改写)")
    retriever = FakeRetriever(chunks=[_CHUNK])
    service = ChatService(
        session=db_session,
        retriever=retriever,
        llm=FakeChatLLM(),
        query_rewriter=rewriter,
    )

    first = await service.chat(ChatRequest(message="第一问", user_id="u1"))
    await service.chat(ChatRequest(message="它支持哪些步骤", session_id=first.session_id))

    # 仅第二轮有历史才改写
    assert len(rewriter.calls) == 1
    assert rewriter.calls[0][0] == "它支持哪些步骤"
    assert retriever.calls[-1]["query"] == "报销流程的具体步骤(改写)"
    # 第一轮检索仍用原始 query
    assert retriever.calls[0]["query"] == "第一问"


async def test_chat_rewrite_failure_falls_back(db_session: AsyncSession) -> None:
    """改写失败时回退原 query, 对话不中断."""
    retriever = FakeRetriever(chunks=[_CHUNK])
    service = ChatService(
        session=db_session,
        retriever=retriever,
        llm=FakeChatLLM(),
        query_rewriter=_BoomQueryRewriter(),
    )

    first = await service.chat(ChatRequest(message="第一问", user_id="u1"))
    resp = await service.chat(ChatRequest(message="第二问", session_id=first.session_id))

    assert resp.answer == "这是来自 KnowFlow 的回复。"
    assert retriever.calls[-1]["query"] == "第二问"


async def test_chat_session_not_found(db_session: AsyncSession) -> None:
    """指定不存在的 session_id 抛 NotFoundError."""
    with pytest.raises(NotFoundError):
        await _service(db_session).chat(ChatRequest(message="hi", session_id="999"))


async def test_chat_invalid_session_id(db_session: AsyncSession) -> None:
    """非法 session_id 抛 ValidationError."""
    with pytest.raises(ValidationError):
        await _service(db_session).chat(ChatRequest(message="hi", session_id="abc"))


async def test_stream_events_sequence(db_session: AsyncSession) -> None:
    """流式事件序列: retrieval → token* → done, done 含引用与耗时."""
    events = []
    async for e in _service(db_session).stream_events(
        ChatRequest(message="报销流程", user_id="u1")
    ):
        events.append(e)

    types = [e["event"] for e in events]
    assert types[0] == "retrieval"
    assert "token" in types
    assert types[-1] == "done"

    retrieval = json.loads(events[0]["data"])
    assert retrieval["chunks"][0]["chunk_id"] == 1

    tokens = [json.loads(e["data"])["delta"] for e in events if e["event"] == "token"]
    assert "".join(tokens) == "这是来自KnowFlow的回复。"

    done = json.loads(events[-1]["data"])
    assert done["session_id"].isdigit()
    assert done["citations"][0]["chunk_id"] == 1
    assert done["latency_ms"] >= 0


async def test_stream_persists_messages_and_turn(db_session: AsyncSession) -> None:
    """流式结束: assistant 消息与轮次落库."""
    events = []
    async for e in _service(db_session).stream_events(ChatRequest(message="你好", user_id="u1")):
        events.append(e)

    done = json.loads(events[-1]["data"])
    messages = await MessageRepo(db_session).list_by_session(int(done["session_id"]))
    assert len(messages) == 2
    assert messages[1].role == "assistant"
    turns = await TurnRepo(db_session).list_by_session(int(done["session_id"]))
    assert len(turns) == 1


async def test_stream_error_event(db_session: AsyncSession) -> None:
    """LLM 流式异常: 最后事件为 error 且不抛给调用方."""
    llm = FakeChatLLM(raise_on_stream=True)
    events = []
    async for e in _service(db_session, llm).stream_events(ChatRequest(message="hi", user_id="u1")):
        events.append(e)

    assert events[-1]["event"] == "error"
    assert "failed" in json.loads(events[-1]["data"])["error"]


# ── 工具链路(orchestrator 注入) ──


def _tool_record(**kw: object) -> ToolCallRecord:
    """构造一条工具调用记录(默认 calculator 成功)."""
    fields = {"latency_ms": 12.3, **kw}
    return ToolCallRecord(
        tool_name="calculator",
        args={"expression": "2**10"},
        success=True,
        output=1024,
        **fields,
    )


async def test_chat_with_orchestrator_runs_tools(db_session: AsyncSession) -> None:
    """工具链路同步: orchestrator 执行工具调用, 响应含 tool_calls 且随消息落库."""
    orc = FakeToolOrchestrator(answer="2 的 10 次方是 1024。", tool_calls=[_tool_record()])
    llm = FakeChatLLM()
    resp = await _service(db_session, llm, orchestrator=orc).chat(
        ChatRequest(message="帮我算 2 的 10 次方", user_id="u1")
    )

    assert resp.answer == "2 的 10 次方是 1024。"
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["tool"] == "calculator"
    assert resp.tool_calls[0]["success"] is True
    # 直连 LLM 未被调用(工具链路接管), 预检索上下文已注入编排器
    assert llm.invoke_calls == 0
    assert orc.run_calls[0]["context"] == "[1] 报销流程: 填写报销单并提交部门审批。"

    messages = await MessageRepo(db_session).list_by_session(int(resp.session_id))
    assert messages[1].citations["tool_calls"][0]["tool"] == "calculator"


async def test_chat_with_orchestrator_no_tools_falls_back(db_session: AsyncSession) -> None:
    """无可见工具时回退直连链路: 答案来自 LLM, 无工具记录."""
    orc = FakeToolOrchestrator(no_tools=True)
    llm = FakeChatLLM()
    resp = await _service(db_session, llm, orchestrator=orc).chat(
        ChatRequest(message="报销流程是什么?", user_id="u1")
    )

    assert resp.answer == llm.answer
    assert resp.tool_calls == []
    assert llm.invoke_calls == 1


async def test_stream_with_orchestrator_tool_events(db_session: AsyncSession) -> None:
    """工具链路流式: retrieval → tool_start → tool_end → token(整段答案) → done."""
    orc = FakeToolOrchestrator(answer="计算结果: 1024", tool_calls=[_tool_record(latency_ms=5.0)])
    events = []
    async for e in _service(db_session, orchestrator=orc).stream_events(
        ChatRequest(message="帮我算 2 的 10 次方", user_id="u1")
    ):
        events.append(e)

    types = [e["event"] for e in events]
    assert types == ["retrieval", "tool_start", "tool_end", "token", "done"]
    assert json.loads(events[2]["data"])["success"] is True
    assert json.loads(events[3]["data"])["delta"] == "计算结果: 1024"
    done = json.loads(events[-1]["data"])
    assert done["tool_calls"][0]["tool"] == "calculator"


async def test_stream_with_orchestrator_no_tools_falls_back(db_session: AsyncSession) -> None:
    """无可见工具流式回退: 保持逐 token 事件序列."""
    orc = FakeToolOrchestrator(no_tools=True)
    events = []
    async for e in _service(db_session, orchestrator=orc).stream_events(
        ChatRequest(message="报销流程?", user_id="u1")
    ):
        events.append(e)

    types = [e["event"] for e in events]
    assert types[0] == "retrieval"
    assert types[-1] == "done"
    assert sum(1 for t in types if t == "token") == 4  # FakeChatLLM.token_chunks 4 段
    assert "tool_start" not in types


class _StreamingToolOrchestrator(FakeToolOrchestrator):
    """fake 工具编排器: 调用 on_tool/on_token 回调, 模拟真实流式行为."""

    answer = "计算结果: 1024"

    async def run(
        self,
        query,
        session_id=None,
        agent_role=None,
        history=None,
        context=None,
        active_skills=None,
        on_token=None,
        on_tool=None,
    ):
        from knowflow.services.tool_orchestrator import OrchestratorResult

        if on_tool is not None:
            await on_tool(self.tool_calls[0])
        if on_token is not None:
            for part in ("计算结果", ": ", "1024"):
                await on_token(part)
        return OrchestratorResult(
            answer=self.answer, tool_calls=list(self.tool_calls), no_tools=self.no_tools
        )


async def test_stream_orchestrator_callbacks_forwarded(db_session: AsyncSession) -> None:
    """工具链路真流式: 编排器回调的 tool/token 事件逐段转发, 不重复整段."""
    orc = _StreamingToolOrchestrator(tool_calls=[_tool_record(latency_ms=5.0)])
    events = []
    async for e in _service(db_session, orchestrator=orc).stream_events(
        ChatRequest(message="帮我算 2 的 10 次方", user_id="u1")
    ):
        events.append(e)

    types = [e["event"] for e in events]
    assert types == ["retrieval", "tool_start", "tool_end", "token", "token", "token", "done"]
    # 逐段 token 拼接等于完整答案, 且未重复整段回传
    deltas = [json.loads(e["data"])["delta"] for e in events if e["event"] == "token"]
    assert "".join(deltas) == "计算结果: 1024"
    assert len(deltas) == 3


# ── 记忆集成(memory_manager 注入) ──


def _memory_service(
    session: AsyncSession,
    memory: FakeMemoryManager | None = None,
    llm: FakeChatLLM | None = None,
) -> ChatService:
    return ChatService(
        session=session,
        retriever=FakeRetriever(chunks=[_CHUNK]),
        llm=llm or FakeChatLLM(),
        memory_manager=memory or FakeMemoryManager(),
    )


async def test_chat_observes_user_and_assistant_messages(db_session: AsyncSession) -> None:
    """对话中 user/assistant 消息均写入短期记忆."""
    memory = FakeMemoryManager()
    resp = await _memory_service(db_session, memory).chat(
        ChatRequest(message="报销流程是什么?", user_id="u1")
    )

    roles = [r for _, r, _ in memory.observed]
    assert roles == ["user", "assistant"]
    assert memory.observed[0][2] == "报销流程是什么?"
    assert memory.observed[1][2] == resp.answer


async def test_chat_sediments_on_interval(db_session: AsyncSession) -> None:
    """每 N 轮对话触发一次沉淀(assistant 落库后)."""
    memory = FakeMemoryManager(interval=5)
    service = _memory_service(db_session, memory)
    sid = None
    for _ in range(5):
        resp = await service.chat(ChatRequest(message="你好", session_id=sid, user_id="u1"))
        sid = resp.session_id

    assert len(memory.sediment_calls) == 1
    assert memory.sediment_calls[0][1] == "u1"


async def test_chat_recalls_memory_and_injects_prompt(db_session: AsyncSession) -> None:
    """对话前召回用户长期记忆, 注入系统提示(直连链路)."""
    memory = FakeMemoryManager(recalled=[object()], recalled_text="- 用户偏好简洁回答")
    llm = FakeChatLLM()
    await _memory_service(db_session, memory, llm).chat(
        ChatRequest(message="报销流程是什么?", user_id="u1")
    )

    assert len(memory.recall_calls) == 1
    assert memory.recall_calls[0] == ("报销流程是什么?", "u1")
    system = llm.last_messages[0]["content"]
    assert "用户记忆" in system
    assert "- 用户偏好简洁回答" in system


async def test_chat_no_recall_without_user_id(db_session: AsyncSession) -> None:
    """无 user_id 时不召回记忆(匿名会话), 记忆文本为空."""
    memory = FakeMemoryManager()
    await _memory_service(db_session, memory).chat(ChatRequest(message="你好"))
    assert memory.recall_calls == []


async def test_chat_empty_retrieval_allows_llm_knowledge(db_session: AsyncSession) -> None:
    """检索结果为空时: 系统提示允许 LLM 用自身知识回答(不再要求拒答)."""
    llm = FakeChatLLM()
    retriever = FakeRetriever(chunks=[])  # 空检索
    service = ChatService(
        session=db_session,
        retriever=retriever,
        llm=llm,
    )
    resp = await service.chat(ChatRequest(message="员工报销流程是什么?", user_id="u1"))

    assert resp.answer == llm.answer
    system = llm.last_messages[0]["content"]
    # 提示词明确允许用自身知识兜底, 且上下文标注未检索到
    assert "可用自身知识回答" in system
    assert "知识库未检索到相关内容" in system
    assert resp.citations == []


# ── Multi-Agent 编排接入 ──


async def test_chat_uses_multi_agent_for_complex_task(db_session: AsyncSession) -> None:
    """复杂任务走多 Agent 编排: 编排答案落库, 不再调直连 LLM."""
    llm = FakeChatLLM()
    multi = FakeMultiAgentOrchestrator(answer="A 售价 100, B 售价 200")
    resp = await _service(db_session, llm, multi_agent=multi).chat(
        ChatRequest(message="对比 A 和 B 的价格", user_id="u1")
    )

    assert resp.answer == "A 售价 100, B 售价 200"
    assert len(resp.citations) == 1  # 检索引用仍返回
    assert llm.invoke_calls == 0  # 编排链路不调直连 LLM
    assert len(multi.run_calls) == 1
    assert multi.run_calls[0]["query"] == "对比 A 和 B 的价格"
    assert "报销流程" in multi.run_calls[0]["context"]  # 预检索上下文注入

    messages = await MessageRepo(db_session).list_by_session(int(resp.session_id))
    assert messages[1].content == "A 售价 100, B 售价 200"


async def test_chat_falls_back_to_direct_when_intent_simple(db_session: AsyncSession) -> None:
    """编排器返回 simple 信号(无 answer)时回退直连 LLM 链路."""
    llm = FakeChatLLM()
    multi = FakeMultiAgentOrchestrator(intent="simple", answer="")
    resp = await _service(db_session, llm, multi_agent=multi).chat(
        ChatRequest(message="你好", user_id="u1")
    )

    assert resp.answer == llm.answer
    assert llm.invoke_calls == 1
    assert len(multi.run_calls) == 1


async def test_chat_stream_multi_agent_emits_progress_and_token(db_session: AsyncSession) -> None:
    """流式链路: 编排结果以 progress + token 事件回传, done 收尾."""
    multi = FakeMultiAgentOrchestrator(answer="汇总答案")
    service = _service(db_session, multi_agent=multi)
    events = [
        e
        async for e in service.stream_events(
            ChatRequest(message="对比 A 和 B 的价格", user_id="u1")
        )
    ]
    types = [e["event"] for e in events]
    assert "retrieval" in types
    assert "progress" in types
    assert "token" in types
    assert types[-1] == "done"
    progress = next(e for e in events if e["event"] == "progress")
    progress_data = json.loads(progress["data"])
    assert progress_data["stage"] == "multi_agent"
    assert progress_data["delegated"] is True


async def test_chat_multi_agent_failure_falls_back_to_direct(db_session: AsyncSession) -> None:
    """编排运行失败(如 checkpoint PG 不可用)时回退直连链路, 不中断对话."""
    llm = FakeChatLLM()
    multi = FakeMultiAgentOrchestrator(raise_failure=True)
    resp = await _service(db_session, llm, multi_agent=multi).chat(
        ChatRequest(message="对比 A 和 B 的价格", user_id="u1")
    )

    assert resp.answer == llm.answer  # 直连链路兜底
    assert llm.invoke_calls == 1
    assert len(multi.run_calls) == 1  # 编排确实被调用过, 只是失败降级


async def test_chat_stream_multi_agent_failure_falls_back(db_session: AsyncSession) -> None:
    """流式链路: 编排失败回退直连, 事件序列仍以 done 收尾(无 progress)."""
    llm = FakeChatLLM()
    multi = FakeMultiAgentOrchestrator(raise_failure=True)
    service = _service(db_session, llm, multi_agent=multi)
    events = [
        e
        async for e in service.stream_events(
            ChatRequest(message="对比 A 和 B 的价格", user_id="u1")
        )
    ]
    types = [e["event"] for e in events]
    assert "progress" not in types
    assert "token" in types
    assert types[-1] == "done"


class _StreamingMultiAgent(FakeMultiAgentOrchestrator):
    """fake 多 Agent 编排器: 调用 on_progress/on_token 回调, 模拟真实流式行为."""

    async def run(
        self, query, session_id=None, context="", history=None, on_token=None, on_progress=None
    ):
        from knowflow.agents.orchestrator import MultiAgentResult

        if on_progress is not None:
            await on_progress({"delegated": True, "subtasks": ["t1", "t2"], "run_id": 1})
        if on_token is not None:
            for part in ("汇总", "答案"):
                await on_token(part)
        return MultiAgentResult(
            run_id=1,
            delegated=True,
            answer=self.answer,
            intent="complex",
            subtasks=list(self.subtasks),
            checkpoint_id="ckpt-1",
            latency_ms=10.0,
        )


async def test_chat_stream_multi_agent_callbacks_forwarded(db_session: AsyncSession) -> None:
    """Multi-Agent 链路真流式: progress 先于逐段 token, 且不重复整段回传."""
    multi = _StreamingMultiAgent(answer="汇总答案")
    service = _service(db_session, multi_agent=multi)
    events = [
        e
        async for e in service.stream_events(
            ChatRequest(message="对比 A 和 B 的价格", user_id="u1")
        )
    ]
    types = [e["event"] for e in events]
    assert types[0] == "retrieval"
    assert types[1] == "progress"  # 回调进度先于 token 流
    assert types[-1] == "done"
    deltas = [json.loads(e["data"])["delta"] for e in events if e["event"] == "token"]
    assert "".join(deltas) == "汇总答案"
    assert len(deltas) == 2


async def test_chat_multi_agent_receives_history(db_session: AsyncSession) -> None:
    """编排器收到最近对话历史(主 Agent 直答链路保持多轮上下文)."""
    llm = FakeChatLLM()
    multi = FakeMultiAgentOrchestrator()
    service = _service(db_session, llm, multi_agent=multi)
    first = await service.chat(ChatRequest(message="第一问", user_id="u1"))
    await service.chat(
        ChatRequest(message="对比 A 和 B 的价格", session_id=first.session_id, user_id="u1")
    )

    history = multi.run_calls[-1]["history"]
    assert history  # 历史非空
    assert any(m["role"] == "user" and "第一问" in m["content"] for m in history)
    assert any(m["role"] == "assistant" for m in history)
