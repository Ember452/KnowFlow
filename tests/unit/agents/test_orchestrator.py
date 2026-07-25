"""MultiAgentOrchestrator 单测 - 委派/并发/降级/落库/checkpoint 全链路.

使用 SQLite(StaticPool 共享内存库) + InMemorySaver, 不依赖真实 PG/LLM.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from knowflow.agents.checkpoint import CheckpointManager
from knowflow.agents.orchestrator import MultiAgentOrchestrator
from knowflow.db.repositories.agent_repo import AgentRunRepo, TaskDelegationRepo
from knowflow.db.repositories.session_repo import SessionRepo
from knowflow.models import Base
from knowflow.retrieval.retriever import ChunkWithScore, RetrievalResult
from knowflow.tools.domain import AgentRole
from tests.fakes import FakeToolOrchestrator

PLAN_DELEGATE = (
    '{"needs_delegation": true, "reason": "可拆分", '
    '"subtasks": [{"id": "t1", "task": "查询产品 A 的价格"}, '
    '{"id": "t2", "task": "查询产品 B 的价格"}]}'
)
PLAN_DIRECT = '{"needs_delegation": false, "reason": "单一问答", "subtasks": []}'


class RoutingFakeLLM:
    """按 prompt 内容路由响应的 fake LLM(并发子任务顺序无关).

    ainvoke 兼容 str(plan/summarize 直传 prompt)与 list(messages) 两种调用形态.
    """

    def __init__(
        self,
        plan_json: str = PLAN_DELEGATE,
        sub_outputs: dict[str, str] | None = None,
        summary: str = "汇总答案",
        direct: str = "直答答案",
        fail_tasks: set[str] | None = None,
    ) -> None:
        self.plan_json = plan_json
        # 子任务输出加长到真实输出量级(>=20 字符), 避免触发质量门禁重试
        self.sub_outputs = sub_outputs or {
            "产品 A": "产品 A 的当前售价为 100 元 性价比很高",
            "产品 B": "产品 B 的当前售价为 200 元 性价比很高",
        }
        self.summary = summary
        self.direct = direct
        self.fail_tasks = fail_tasks or set()
        self.calls: list[object] = []

    async def ainvoke(self, messages: object) -> str:
        self.calls.append(messages)
        prompt = messages if isinstance(messages, str) else str(messages)
        if "将用户任务拆解" in prompt:  # 规划 prompt
            return self.plan_json
        if "汇总子 Agent 的执行结果" in prompt:  # 汇总 prompt(先于"子 Agent"判断)
            return self.summary
        if "子 Agent" in prompt:  # 子任务执行 prompt
            for key, out in self.sub_outputs.items():
                if key in prompt:
                    if key in self.fail_tasks:
                        raise RuntimeError(f"子任务 {key} 执行失败")
                    return out
            return "默认子结果"
        return self.direct  # 直答


class FakeRetriever:
    """按 query 返回 chunk 内容的 fake 检索器(记录 query 供断言)."""

    def __init__(
        self,
        chunks_by_query: dict[str, list[str]] | None = None,
        fail: bool = False,
    ) -> None:
        self.chunks_by_query = chunks_by_query or {}
        self.fail = fail
        self.queries: list[str] = []

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        with_expand: bool = True,
        with_rerank: bool = True,
    ) -> RetrievalResult:
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("检索服务不可用")
        contents = self.chunks_by_query.get(query, [])
        return RetrievalResult(
            query=query,
            chunks=[
                ChunkWithScore(chunk_id=i, content=c, score=1.0, source="test")
                for i, c in enumerate(contents)
            ],
        )


class AttemptFakeLLM(RoutingFakeLLM):
    """子任务首次失败/输出过短、重试成功的 fake(并发顺序无关: 按任务统计次数)."""

    def __init__(
        self,
        fail_once: set[str] | None = None,
        short_once: set[str] | None = None,
        summary: str = "汇总答案",
    ) -> None:
        super().__init__(plan_json=PLAN_DELEGATE, summary=summary)
        self.fail_once = fail_once or set()
        self.short_once = short_once or set()
        self.task_calls: dict[str, int] = {}

    async def ainvoke(self, messages: object) -> str:
        self.calls.append(messages)
        prompt = messages if isinstance(messages, str) else str(messages)
        if "将用户任务拆解" in prompt:
            return self.plan_json
        if "汇总子 Agent 的执行结果" in prompt:
            return self.summary
        if "子 Agent" in prompt:
            # 按子任务主题计数(产品 A/B), 与 fail_once/short_once 判定解耦
            key = next((k for k in ("产品 A", "产品 B") if k in prompt), None)
            if key is not None:
                count = self.task_calls.get(key, 0) + 1
                self.task_calls[key] = count
                if count == 1 and key in self.fail_once:
                    raise RuntimeError(f"子任务 {key} 执行失败")
                if count == 1 and key in self.short_once:
                    return "短"  # 过短触发质量门禁重试
            return "子任务的有效输出内容已生成并可以用于最终汇总"
        return self.direct


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """StaticPool 共享内存 SQLite: 跨 session 数据一致(编排器多事务)."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


def _build_orchestrator(
    llm: RoutingFakeLLM, session_factory: async_sessionmaker[AsyncSession]
) -> MultiAgentOrchestrator:
    return MultiAgentOrchestrator(
        llm=llm,
        session_factory=session_factory,
        checkpoints=CheckpointManager(saver=InMemorySaver()),
    )


async def _create_session(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        sess = await SessionRepo(session).create(user_id="u1")
        await session.commit()
        return int(sess.id)


# ── 意图路由 ──


@pytest.mark.asyncio
async def test_run_simple_intent_returns_direct_signal() -> None:
    """simple 问题: 不建 run, 返回空 answer 供调用方直连."""
    llm = RoutingFakeLLM()
    orc = MultiAgentOrchestrator(llm=llm, session_factory=None)
    result = await orc.run("公司报销流程是什么?", session_id=None, context="")
    assert result.intent == "simple"
    assert result.delegated is False
    assert result.answer == ""
    assert result.run_id is None
    assert llm.calls == []  # 未调 LLM


# ── 委派全链路 ──


@pytest.mark.asyncio
async def test_run_delegation_full_chain(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """complex 委派: 父/子 runs + delegations 落库 + 汇总答案 + checkpoint."""
    llm = RoutingFakeLLM()
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id, context="产品资料")
    assert result.intent == "complex"
    assert result.delegated is True
    assert result.answer == "汇总答案"
    assert result.run_id is not None
    assert len(result.subtasks) == 2
    assert all(s.status == "completed" for s in result.subtasks)
    assert result.checkpoint_id is not None

    # 父子 run 落库
    async with session_factory() as session:
        run_repo = AgentRunRepo(session)
        main = await run_repo.get(int(result.run_id))
        assert main is not None
        assert main.agent_type == "main"
        assert main.status == "completed"
        children = await run_repo.list_children(int(result.run_id))
        assert len(children) == 2
        assert all(c.agent_type == "sub" and c.status == "completed" for c in children)
        # 委派记录
        del_repo = TaskDelegationRepo(session)
        delegations = await del_repo.list_by_parent(int(result.run_id))
        assert len(delegations) == 2
        assert all(d.status == "completed" for d in delegations)
        # 全部委派指向同一 execute 里程碑(execute_node 内落库), 早于结果标记
        assert len({d.checkpoint_id for d in delegations}) == 1
        milestone_id = delegations[0].checkpoint_id
        assert milestone_id != result.checkpoint_id
        assert {d.task for d in delegations} == {"查询产品 A 的价格", "查询产品 B 的价格"}

    # checkpoint lineage 链完整: 链头为线程最新(编排结果标记), 委派里程碑可按 id 恢复
    chain = await orc._checkpoints.lineage(str(result.run_id))  # type: ignore[union-attr]
    assert len(chain) >= 3  # 运行时节点边界 checkpoint 成链
    assert chain[0]["checkpoint_id"] == result.checkpoint_id
    milestone = await orc._checkpoints.restore(str(result.run_id), milestone_id)
    assert milestone is not None and "subtask_results" in milestone
    assert {s["subtask_id"] for s in milestone["subtask_results"]} == {"t1", "t2"}

    # 预检索上下文真正进入子 Agent(regression: schema 外键曾被 LangGraph 丢弃)
    sub_calls = [c for c in llm.calls if isinstance(c, list)]
    assert sub_calls, "子 Agent 应收到消息列表"
    assert any("产品资料" in str(c) for c in sub_calls)


@pytest.mark.asyncio
async def test_run_llm_no_delegation_direct(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """complex 但 LLM 判定无需委派: 直答, 无子 run."""
    llm = RoutingFakeLLM(plan_json=PLAN_DIRECT)
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    result = await orc.run("分析这个产品的优缺点", session_id=session_id, context="资料")
    assert result.delegated is False
    assert result.answer == "直答答案"
    assert result.subtasks == []
    assert result.run_id is not None

    async with session_factory() as session:
        run_repo = AgentRunRepo(session)
        assert await run_repo.list_children(int(result.run_id)) == []
        del_repo = TaskDelegationRepo(session)
        assert await del_repo.list_by_parent(int(result.run_id)) == []


@pytest.mark.asyncio
async def test_run_direct_answer_injects_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """直答链路注入最近对话历史(多轮上下文保持)."""
    llm = RoutingFakeLLM(plan_json=PLAN_DIRECT)
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)
    history = [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "第一答"},
    ]

    result = await orc.run(
        "对比 A 和 B 的价格", session_id=session_id, context="资料", history=history
    )
    assert result.answer == "直答答案"
    # 最后一次调用为直答(消息列表形态), 含 system + 历史 + 当前问题
    direct_call = llm.calls[-1]
    assert isinstance(direct_call, list)
    assert len(direct_call) == 4
    assert direct_call[1:3] == history
    assert direct_call[-1] == {"role": "user", "content": "对比 A 和 B 的价格"}


# ── 降级 ──


@pytest.mark.asyncio
async def test_run_subtask_failure_degrades(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """单个子任务失败不阻塞整体: 对应 subtask failed, 主 run 仍 completed."""
    llm = RoutingFakeLLM(fail_tasks={"产品 B"})
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id)
    assert result.delegated is True
    assert result.answer == "汇总答案"
    statuses = {s.id: s.status for s in result.subtasks}
    assert statuses["t1"] == "completed"
    assert statuses["t2"] == "failed"
    assert result.subtasks[1].error is not None

    async with session_factory() as session:
        run_repo = AgentRunRepo(session)
        main = await run_repo.get(int(result.run_id))
        assert main is not None and main.status == "completed"
        del_repo = TaskDelegationRepo(session)
        delegations = await del_repo.list_by_parent(int(result.run_id))
        assert {d.status for d in delegations} == {"completed", "failed"}


# ── 子任务按需检索 ──


@pytest.mark.asyncio
async def test_run_subtask_on_demand_retrieval(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """子任务按需检索: 各子任务用自己的文本检索, 替换共享预检索上下文."""
    llm = RoutingFakeLLM()
    retriever = FakeRetriever(
        chunks_by_query={
            "查询产品 A 的价格": ["A 的详细资料: 售价 100 元"],
            "查询产品 B 的价格": ["B 的详细资料: 售价 200 元"],
        }
    )
    orc = MultiAgentOrchestrator(
        llm=llm,
        session_factory=session_factory,
        checkpoints=CheckpointManager(saver=InMemorySaver()),
        retriever=retriever,
    )
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id, context="共享产品资料")
    assert result.delegated is True
    # 每个子任务独立检索一次(子任务文本作为 query)
    assert sorted(retriever.queries) == ["查询产品 A 的价格", "查询产品 B 的价格"]
    # 子 Agent 收到的是按需检索结果, 而非共享上下文
    sub_calls = [c for c in llm.calls if isinstance(c, list)]
    assert any("A 的详细资料" in str(c) for c in sub_calls)
    assert any("B 的详细资料" in str(c) for c in sub_calls)
    assert not any("共享产品资料" in str(c) for c in sub_calls)


@pytest.mark.asyncio
async def test_run_subtask_retrieval_fallback_on_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """按需检索抛异常 → 回退共享上下文, 子任务仍成功(检索不阻塞)."""
    llm = RoutingFakeLLM()
    orc = MultiAgentOrchestrator(
        llm=llm,
        session_factory=session_factory,
        checkpoints=CheckpointManager(saver=InMemorySaver()),
        retriever=FakeRetriever(fail=True),
    )
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id, context="共享产品资料")
    assert all(s.status == "completed" for s in result.subtasks)
    sub_calls = [c for c in llm.calls if isinstance(c, list)]
    assert any("共享产品资料" in str(c) for c in sub_calls)


@pytest.mark.asyncio
async def test_run_subtask_retrieval_fallback_on_empty(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """按需检索无结果 → 回退共享上下文."""
    llm = RoutingFakeLLM()
    orc = MultiAgentOrchestrator(
        llm=llm,
        session_factory=session_factory,
        checkpoints=CheckpointManager(saver=InMemorySaver()),
        retriever=FakeRetriever(chunks_by_query={}),
    )
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id, context="共享产品资料")
    assert all(s.status == "completed" for s in result.subtasks)
    sub_calls = [c for c in llm.calls if isinstance(c, list)]
    assert any("共享产品资料" in str(c) for c in sub_calls)


# ── 失败重试与质量门禁 ──


@pytest.mark.asyncio
async def test_run_subtask_retry_success_after_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """子任务首次执行失败 → 携带原因重试 → 成功, 不降级."""
    llm = AttemptFakeLLM(fail_once={"产品 A"})
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id)
    assert all(s.status == "completed" for s in result.subtasks)
    # A 失败 1 次 + 重试 1 次, B 首次即成功
    assert llm.task_calls == {"产品 A": 2, "产品 B": 1}
    # 重试调用携带上次失败原因
    retry_calls = [c for c in llm.calls if "上次执行失败" in str(c)]
    assert retry_calls and "产品 A" in str(retry_calls[0])


@pytest.mark.asyncio
async def test_run_subtask_retry_success_after_quality_gate(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """子任务输出过短(质量门禁未通过) → 重试成功."""
    llm = AttemptFakeLLM(short_once={"产品 A"})
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id)
    assert all(s.status == "completed" for s in result.subtasks)
    assert llm.task_calls == {"产品 A": 2, "产品 B": 1}
    # 质量门禁原因注入重试调用
    retry_calls = [c for c in llm.calls if "上次执行未产出有效结果" in str(c)]
    assert retry_calls and "输出过短" in str(retry_calls[0])


@pytest.mark.asyncio
async def test_run_subtask_retry_exhausted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """重试仍失败 → 子任务 failed, 错误包含尝试次数(降级不阻塞整体)."""
    llm = RoutingFakeLLM(fail_tasks={"产品 B"})
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    result = await orc.run("对比 A 和 B 的价格", session_id=session_id)
    statuses = {s.id: s.status for s in result.subtasks}
    assert statuses["t1"] == "completed"
    assert statuses["t2"] == "failed"
    assert "2 次" in (result.subtasks[1].error or "")


# ── 子 Agent 工具化 ──


@pytest.mark.asyncio
async def test_run_subagent_tool_calls_recorded(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """注入 tool_orchestrator 后子 Agent 走工具循环: 结果带 tool_calls, on_tool 标注 subtask_id."""
    from knowflow.services.tool_orchestrator import ToolCallRecord

    llm = RoutingFakeLLM()
    tool_orc = FakeToolOrchestrator(answer="产品 A 售价 100 元, 数据来自计算器")
    tool_orc.tool_calls = [
        ToolCallRecord(
            tool_name="calculator",
            args={"expression": "100*1"},
            success=True,
            output=100,
            latency_ms=1.5,
        )
    ]
    orc = MultiAgentOrchestrator(
        llm=llm,
        session_factory=session_factory,
        checkpoints=CheckpointManager(saver=InMemorySaver()),
        tool_orchestrator=tool_orc,
    )
    session_id = await _create_session(session_factory)
    tool_events: list[ToolCallRecord] = []

    async def on_tool(record: ToolCallRecord) -> None:
        tool_events.append(record)

    result = await orc.run(
        "对比 A 和 B 的价格", session_id=session_id, context="资料", on_tool=on_tool
    )
    assert result.delegated is True
    assert all(s.status == "completed" for s in result.subtasks)
    # 子任务结果携带工具调用记录
    assert all(len(s.tool_calls) >= 1 for s in result.subtasks)
    # on_tool 上抛的记录标注来源子任务, 子 Agent 以 SUBAGENT 角色运行
    assert len(tool_events) >= 1
    assert tool_events[0].subtask_id in ("t1", "t2")
    assert all(c["agent_role"] == AgentRole.SUBAGENT for c in tool_orc.run_calls)


@pytest.mark.asyncio
async def test_plan_injects_subagent_tools_text(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """规划 prompt 注入子 Agent 可用工具清单(任务可行性判断)."""
    llm = RoutingFakeLLM()
    orc = MultiAgentOrchestrator(
        llm=llm,
        session_factory=session_factory,
        checkpoints=CheckpointManager(saver=InMemorySaver()),
        tool_orchestrator=FakeToolOrchestrator(answer="子任务有效输出内容"),
    )
    session_id = await _create_session(session_factory)

    await orc.run("对比 A 和 B 的价格", session_id=session_id)
    plan_call = next(c for c in llm.calls if isinstance(c, str) and "将用户任务拆解" in c)
    assert "子 Agent 可用工具" in plan_call
    assert "calculator" in plan_call


@pytest.mark.asyncio
async def test_plan_without_tool_orchestrator_marks_no_tools(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """未注入 tool_orchestrator 时规划 prompt 提示子 Agent 无工具(降级)."""
    llm = RoutingFakeLLM()
    orc = _build_orchestrator(llm, session_factory)
    session_id = await _create_session(session_factory)

    await orc.run("对比 A 和 B 的价格", session_id=session_id)
    plan_call = next(c for c in llm.calls if isinstance(c, str) and "将用户任务拆解" in c)
    assert "子 Agent 无工具" in plan_call


# ── graph 条件路由 ──


@pytest.mark.asyncio
async def test_graph_conditional_route_delegate() -> None:
    """needs_delegation=true 时走 execute 节点(execute 用 spy 拦截, 不跑 DB)."""
    from knowflow.agents.graph import build_agent_graph

    visited: list[str] = []
    orc = _build_orchestrator(RoutingFakeLLM(), session_factory=None)  # type: ignore[arg-type]

    def spy(name: str, fn: object) -> object:
        async def wrapped(state: dict) -> dict:  # type: ignore[no-untyped-def]
            visited.append(name)
            if name == "execute":
                return {"subtask_results": []}  # 路由验证只需记录访问
            return await fn(state)  # type: ignore[misc]

        return wrapped

    graph = build_agent_graph(orc, checkpointer=InMemorySaver(), node_factory=spy)
    await graph.ainvoke(
        {
            "query": "对比 A 和 B",
            "needs_delegation": True,
            "plan": [{"id": "t1", "task": "查 A"}, {"id": "t2", "task": "查 B"}],
            "subtask_results": [],
            "retrieval_context": "",
            "session_id": None,
            "run_id": None,
        },
        config={"configurable": {"thread_id": "t-delegate", "checkpoint_ns": ""}},
    )
    assert visited == ["understand", "plan", "execute", "summarize"]


@pytest.mark.asyncio
async def test_graph_conditional_route_direct() -> None:
    """needs_delegation=false 时跳过 execute 直接 summarize."""
    from knowflow.agents.graph import build_agent_graph

    visited: list[str] = []
    orc = _build_orchestrator(RoutingFakeLLM(), session_factory=None)  # type: ignore[arg-type]

    def spy(name: str, fn: object) -> object:
        async def wrapped(state: dict) -> dict:  # type: ignore[no-untyped-def]
            visited.append(name)
            return await fn(state)  # type: ignore[misc]

        return wrapped

    graph = build_agent_graph(orc, checkpointer=InMemorySaver(), node_factory=spy)
    await graph.ainvoke(
        {
            "query": "报销流程",
            "needs_delegation": False,
            "plan": [],
            "subtask_results": [],
            "retrieval_context": "",
            "session_id": None,
            "run_id": None,
        },
        config={"configurable": {"thread_id": "t-direct", "checkpoint_ns": ""}},
    )
    assert visited == ["understand", "plan", "summarize"]
