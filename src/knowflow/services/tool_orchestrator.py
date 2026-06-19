"""工具编排器 - 工具版对话链路(意图激活 → 注入可见工具 → LLM 工具调用循环).

run(query, ...): 取激活 Skill → 按执行域计算可见工具 → 注入 LLM(bind_tools) →
循环执行工具调用并回填结果, 直到 LLM 不再调用工具或达到 max_tool_rounds.
每轮经 PermissionChecker 校验越权, ToolMetrics 记录调用.

LLM 协议(duck typing): bind_tools(list[dict]) -> bound; bound.ainvoke(messages)
-> response, response 含 .content(str) 与 .tool_calls(list[{name,args}]).
"""

import time
from dataclasses import dataclass, field
from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import ToolExecutionError
from knowflow.core.logging import get_logger
from knowflow.tools.dependency_resolver import DependencyResolver
from knowflow.tools.domain import AgentRole, filter_skills_by_role
from knowflow.tools.injector import Injector
from knowflow.tools.metrics import ToolMetrics
from knowflow.tools.permission import PermissionChecker
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_manager import SkillManager
from knowflow.tools.visibility import VisibilityCalculator

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "你是 KnowFlow 助手, 可调用工具完成用户任务. "
    "优先调用合适的工具, 工具返回结果后据此作答; 无需工具时直接回答."
)


@dataclass
class ToolCallRecord:
    """单次工具调用记录(供 trace/展示)."""

    tool_name: str
    args: dict[str, Any]
    success: bool
    output: Any
    latency_ms: float
    error: str | None = None


@dataclass
class OrchestratorResult:
    """工具编排结果."""

    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    rounds: int = 0
    truncated: bool = False
    no_tools: bool = False


class ToolOrchestrator:
    """工具版对话编排器. 编排 Skill 激活/可见性/注入/调用循环."""

    def __init__(
        self,
        registry: ToolRegistry,
        skill_manager: SkillManager,
        llm: Any,
        settings: Settings | None = None,
        metrics: ToolMetrics | None = None,
    ) -> None:
        self._registry = registry
        self._skills = skill_manager
        self._llm = llm
        self._settings = settings or get_settings()
        self._visibility = VisibilityCalculator()
        self._injector = Injector()
        self._permission = PermissionChecker(self._visibility)
        self._resolver = DependencyResolver()
        self._metrics = metrics or ToolMetrics()

    async def run(
        self,
        query: str,
        session_id: str | None = None,
        agent_role: AgentRole = AgentRole.MAIN,
        history: list[dict[str, str]] | None = None,
    ) -> OrchestratorResult:
        """执行工具版对话: 激活 Skill → 注入可见工具 → 工具调用循环 → 最终答案."""
        active = filter_skills_by_role(self._skills.active_skills(), agent_role)
        visible = self._visibility.compute(active, agent_role, self._registry)
        if not visible:
            return OrchestratorResult(answer="", no_tools=True)

        tool_defs = self._injector.inject(visible)
        bound = self._llm.bind_tools(tool_defs)
        messages: list[Any] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            *(history or []),
            {"role": "user", "content": query},
        ]

        tool_calls_log: list[ToolCallRecord] = []
        max_rounds = self._settings.max_tool_rounds
        for round_idx in range(max_rounds):
            response = await bound.ainvoke(messages)
            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                answer = getattr(response, "content", "") or str(response)
                return OrchestratorResult(
                    answer=answer,
                    tool_calls=tool_calls_log,
                    rounds=round_idx,
                )
            # 回填 assistant 消息(含 tool_calls), 供 LLM 关联工具结果
            messages.append(response)
            for tc in calls:
                record = await self._invoke_tool(tc, agent_role, active, session_id)
                tool_calls_log.append(record)
                # 工具结果以 tool 消息回填
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id", "")),
                        "name": record.tool_name,
                        "content": str(record.output if record.success else record.error),
                    }
                )

        logger.warning("tool_orchestrator.max_rounds_reached", rounds=max_rounds)
        return OrchestratorResult(
            answer="(已达到最大工具调用轮数, 停止循环)",
            tool_calls=tool_calls_log,
            rounds=max_rounds,
            truncated=True,
        )

    async def _invoke_tool(
        self,
        tool_call: dict[str, Any],
        agent_role: AgentRole,
        active: list,
        session_id: str | None,
    ) -> ToolCallRecord:
        """执行单次工具调用: 权限校验 → 执行 → 记录指标. 越权/失败不中断循环."""
        name = str(tool_call.get("name", ""))
        args = dict(tool_call.get("args", {}) or {})
        # 文件类工具自动补 session_id(若未提供), 便于 LLM 调用
        if session_id is not None and "session_id" in args and not args.get("session_id"):
            args["session_id"] = session_id
        start = time.perf_counter()
        try:
            self._permission.check(name, agent_role, active, self._registry)
            result = await self._registry.get(name).execute(**args)
            latency_ms = (time.perf_counter() - start) * 1000
            self._metrics.record_call(
                name, result.success, result.token_usage, round(latency_ms, 2)
            )
            return ToolCallRecord(
                tool_name=name,
                args=args,
                success=result.success,
                output=result.output,
                latency_ms=round(latency_ms, 2),
                error=result.error,
            )
        except ToolExecutionError as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._metrics.record_call(name, False, 0, round(latency_ms, 2))
            logger.warning("tool_orchestrator.permission_denied", tool=name, error=str(exc))
            return ToolCallRecord(
                tool_name=name,
                args=args,
                success=False,
                output=None,
                latency_ms=round(latency_ms, 2),
                error=str(exc),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            self._metrics.record_call(name, False, 0, round(latency_ms, 2))
            return ToolCallRecord(
                tool_name=name,
                args=args,
                success=False,
                output=None,
                latency_ms=round(latency_ms, 2),
                error=str(exc),
            )
