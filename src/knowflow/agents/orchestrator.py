"""MultiAgentOrchestrator - 复杂任务编排入口.

流程: 规则意图分类(simple 直连/ complex 进状态机) → 创建主 run →
LangGraph 状态机(understand → plan → [execute 并发委派] → summarize) →
父子 run/delegation 落库 + checkpoint 父子链记录.

子 Agent 与主 Agent 上下文隔离(独立 ContextManager 实例, 见 subagent.py);
并发执行走 agents/concurrent.py(asyncio.gather + 超时 + 降级).
"""

import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from knowflow.agents.checkpoint import CheckpointManager
from knowflow.agents.concurrent import SubtaskResult, run_concurrent
from knowflow.agents.delegation import TaskDelegationFactory
from knowflow.agents.main_agent import MainAgent, PlanResult
from knowflow.agents.subagent import Subagent
from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.db.repositories.agent_repo import AgentRunRepo, TaskDelegationRepo

logger = get_logger(__name__)


@dataclass
class SubtaskInfo:
    """子任务执行信息(响应/展示用)."""

    id: str
    task: str
    status: str
    output: str = ""
    error: str | None = None
    run_id: int | None = None
    checkpoint_id: str | None = None
    latency_ms: float = 0.0


@dataclass
class MultiAgentResult:
    """多 Agent 编排结果."""

    run_id: int | None = None
    delegated: bool = False
    answer: str = ""
    intent: str = "simple"
    subtasks: list[SubtaskInfo] = field(default_factory=list)
    checkpoint_id: str | None = None
    latency_ms: float = 0.0


class MultiAgentOrchestrator:
    """多 Agent 编排器. 复杂任务(可拆分)走状态机, 简单任务信号直连."""

    def __init__(
        self,
        llm: Any | None = None,
        settings: Settings | None = None,
        session_factory: Any | None = None,
        checkpoints: CheckpointManager | None = None,
        context_manager: Any | None = None,
    ) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake.
            settings: Settings 单例.
            session_factory: AsyncSession factory(落库 agent_runs/delegations).
            checkpoints: CheckpointManager; None 时新建(生产懒加载 PG).
            context_manager: 子 Agent 独立 ContextManager 实例(可 None).
        """
        self._settings = settings or get_settings()
        self._session_factory: Any = session_factory
        self._checkpoints = checkpoints or CheckpointManager()
        self._main_agent = MainAgent(llm, self._settings)
        self._subagent = Subagent(llm, self._settings, context_manager=context_manager)
        self._graph: Any = None

    # ── 对外入口 ──

    async def run(self, query: str, session_id: int | None, context: str = "") -> MultiAgentResult:
        """编排入口.

        Args:
            query: 用户问题.
            session_id: 会话 id(agent_runs 落库; 直连信号时可不传).
            context: 预检索上下文文本(chat_service 检索后注入).

        Returns:
            MultiAgentResult. intent=simple 时 answer 为空(调用方走直连检索链路);
            委派完成后 answer 为主 Agent 汇总结果.
        """
        start = time.perf_counter()
        intent = self._main_agent.understand(query)
        if intent == "simple":
            return MultiAgentResult(
                intent=intent, latency_ms=round((time.perf_counter() - start) * 1000, 2)
            )
        if session_id is None:
            raise ValueError("complex 任务编排需要 session_id(agent_runs 落库)")

        graph = await self._get_graph()
        async with self._session_factory() as session:
            run_repo = AgentRunRepo(session)
            main_run = await run_repo.create(session_id=int(session_id), agent_type="main")
            await session.commit()
            thread_id = str(main_run.id)
            config = {"configurable": {"thread_id": thread_id}}
            state = {
                "query": query,
                "session_id": int(session_id),
                "run_id": int(main_run.id),
                "retrieval_context": context,
                "agent_role": "main",
                "context_budget": self._settings.context_budget_tokens,
                "active_skills": [],
                "messages": [],
            }
            try:
                final_state = await graph.ainvoke(state, config=config)
                await run_repo.mark_completed(
                    int(main_run.id), "completed", completed_at=datetime.now(UTC)
                )
            except Exception as exc:
                logger.error("multi_agent.run_failed", run_id=int(main_run.id), error=str(exc))
                await run_repo.mark_completed(
                    int(main_run.id), "failed", completed_at=datetime.now(UTC)
                )
                await session.commit()
                raise
            await session.commit()

        # 取线程最新 checkpoint 作为编排结果标记
        ckpt_id: str | None = None
        chain = await self._checkpoints.lineage(thread_id)
        if chain:
            ckpt_id = chain[0]["checkpoint_id"]

        subtask_infos: list[SubtaskInfo] = []
        plan = final_state.get("plan", [])
        for info, sub in zip(final_state.get("subtask_results", []), plan, strict=False):
            subtask_infos.append(
                SubtaskInfo(
                    id=info.get("subtask_id", sub.get("id", "?")),
                    task=sub.get("task", ""),
                    status="completed" if info.get("success") else "failed",
                    output=info.get("output", ""),
                    error=info.get("error"),
                    run_id=info.get("run_id"),
                    checkpoint_id=info.get("checkpoint_id"),
                    latency_ms=info.get("latency_ms", 0.0),
                )
            )
        return MultiAgentResult(
            run_id=int(main_run.id),
            delegated=bool(final_state.get("needs_delegation")),
            answer=final_state.get("final_answer", ""),
            intent=intent,
            subtasks=subtask_infos,
            checkpoint_id=ckpt_id,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    # ── LangGraph 状态机节点 ──

    async def understand_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """understand 节点: 规则意图分类."""
        return {"intent": self._main_agent.understand(state.get("query", ""))}

    async def plan_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """plan 节点: LLM 任务规划(complex 才调 LLM)."""
        if state.get("intent") == "complex":
            plan: PlanResult = await self._main_agent.plan(state.get("query", ""))
        else:
            plan = PlanResult(needs_delegation=False, reason="简单任务无需委派")
        return {"needs_delegation": plan.needs_delegation, "plan": plan.subtasks}

    async def execute_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """execute 节点: 创建子 runs/delegations → 并发执行 → 统一更新状态."""
        plan = state.get("plan", [])
        if not plan:
            return {"subtask_results": []}
        thread_id = str(state["run_id"])
        session_id = int(state["session_id"])
        context = state.get("retrieval_context", "")

        # 1. 创建子 runs + 委派记录(同一事务), 状态推进到 running
        async with self._session_factory() as session:
            run_repo = AgentRunRepo(session)
            factory = TaskDelegationFactory(TaskDelegationRepo(session))
            delegations: list[tuple[dict[str, Any], int, Any]] = []
            for sub in plan:
                sub_run = await run_repo.create(
                    session_id=session_id, agent_type="sub", parent_run_id=state["run_id"]
                )
                delegation = await factory.create(
                    parent_run_id=int(state["run_id"]), task=sub["task"]
                )
                await delegation.mark_delegated(int(sub_run.id))
                await delegation.mark_running()
                delegations.append((sub, int(sub_run.id), delegation))
            await session.commit()

        # 2. 并发执行(无 DB 操作, 各协程独立)
        runners = {
            str(sub["id"]): self._run_subtask(sub, sub_run_id, context)
            for sub, sub_run_id, _ in delegations
        }
        infos = await run_concurrent(runners, timeout=self._settings.agent_timeout_seconds)

        # 3. 记录委派里程碑 checkpoint(断点续跑定位用), 再统一更新委派终态
        milestone = await self._checkpoints.save(
            {**state, "subtask_results": [asdict(i) for i in infos]},
            thread_id,
            metadata={"node": "execute", "run_id": state["run_id"]},
        )
        async with self._session_factory() as session:
            run_repo = AgentRunRepo(session)
            del_repo = TaskDelegationRepo(session)
            for (_, sub_run_id, delegation), info in zip(delegations, infos, strict=True):
                # 子 run 终态与委派终态同步更新
                await run_repo.mark_completed(
                    sub_run_id,
                    "completed" if info.success else "failed",
                    completed_at=datetime.now(UTC),
                )
                if info.success:
                    await del_repo.update_status(
                        delegation.delegation_id,
                        "completed",
                        result={"output": info.output},
                        checkpoint_id=milestone,
                    )
                else:
                    await del_repo.update_status(
                        delegation.delegation_id,
                        "failed",
                        result={"error": info.error},
                        checkpoint_id=milestone,
                    )
            await session.commit()

        return {"subtask_results": [asdict(i) for i in infos]}

    async def summarize_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """summarize 节点: 委派后汇总子结果, 未委派直答."""
        query = state.get("query", "")
        context = state.get("retrieval_context", "")
        if state.get("needs_delegation"):
            answer = await self._main_agent.summarize(query, state.get("subtask_results", []))
        else:
            answer = await self._main_agent.direct_answer(query, context)
        return {"final_answer": answer}

    # ── 内部 ──

    async def _run_subtask(
        self, sub: dict[str, Any], sub_run_id: int, context: str
    ) -> SubtaskResult:
        """单个子任务执行: 子 Agent 独立上下文 → 结果."""
        result = await self._subagent.execute(sub["task"], context)
        return SubtaskResult(
            subtask_id=sub["id"],
            success=True,
            output=result.get("output", ""),
            run_id=sub_run_id,
        )

    async def _get_graph(self) -> Any:
        """惰性编译 LangGraph 状态机(挂 checkpoint saver, 仅编译一次)."""
        if self._graph is None:
            from knowflow.agents.graph import build_agent_graph

            saver = await self._checkpoints.get_saver()
            self._graph = build_agent_graph(self, saver)
            logger.info("multi_agent.graph_compiled")
        return self._graph

    async def dispose(self) -> None:
        """释放 checkpoint 连接池(应用关闭时调用)."""
        await self._checkpoints.dispose()
