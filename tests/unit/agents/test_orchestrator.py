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
        self.sub_outputs = sub_outputs or {"产品 A": "A 售价 100", "产品 B": "B 售价 200"}
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
