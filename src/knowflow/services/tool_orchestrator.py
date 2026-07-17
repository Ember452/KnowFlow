"""工具编排器 - 工具版对话链路(意图激活 → 注入可见工具 → LLM 工具调用循环).

run(query, ...): 取激活 Skill → 按执行域计算可见工具 → 注入 LLM(bind_tools) →
循环执行工具调用并回填结果, 直到 LLM 不再调用工具或达到 max_tool_rounds.
每轮经 PermissionChecker 校验越权, ToolMetrics 记录调用.

LLM 协议(duck typing): bind_tools(list[dict]) -> bound; bound.ainvoke(messages)
-> response, response 含 .content(str) 与 .tool_calls(list[{name,args}]).
"""

import time
from collections.abc import Awaitable, Callable
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
from knowflow.tools.skill_schema import SkillDefinition
from knowflow.tools.visibility import VisibilityCalculator

logger = get_logger(__name__)

_SYSTEM_PROMPT = (
    "你是 KnowFlow 助手, 可调用工具完成用户任务. "
    "优先调用合适的工具, 工具返回结果后据此作答; 无需工具时直接回答."
)

# 检索上下文注入版: 上层(chat_service)预检索后传入, 避免重复调 retrieval_tool
_SYSTEM_PROMPT_WITH_CONTEXT = (
    _SYSTEM_PROMPT + "\n\n检索上下文(优先据此回答, 引用来源用 [n] 标注):\n{context}"
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

    @property
    def metrics(self) -> ToolMetrics:
        """工具调用指标收集器(供治理统计端点读取)."""
        return self._metrics

    async def run(
        self,
        query: str,
        session_id: str | None = None,
        agent_role: AgentRole = AgentRole.MAIN,
        history: list[dict[str, str]] | None = None,
        context: str | None = None,
        active_skills: list[SkillDefinition] | None = None,
        on_token: Callable[[str], Awaitable[None]] | None = None,
        on_tool: Callable[[ToolCallRecord], Awaitable[None]] | None = None,
    ) -> OrchestratorResult:
        """执行工具版对话: 激活 Skill → 注入可见工具 → 工具调用循环 → 最终答案.

        Args:
            query: 用户问题.
            session_id: 会话 id(用于文件类工具自动补参).
            agent_role: 当前 Agent 角色, 决定 subagent_only 域可见性.
            history: 历史消息(role/content).
            context: 检索上下文文本, 注入 system prompt(上层预检索时传入).
            active_skills: 调用方指定的激活 Skill 集; None 时使用管理器全部启用项.
            on_token: 可选流式回调, 最终答案逐段回传(LLM 支持 astream 时);
                None 时一次性返回完整答案.
            on_tool: 可选回调, 每次工具调用完成后通知调用方(事件流展示用).
        """
        if active_skills is None:
            active = filter_skills_by_role(self._skills.active_skills(), agent_role)
        else:
            active = filter_skills_by_role(active_skills, agent_role)
        visible = self._visibility.compute(active, agent_role, self._registry)
        if not visible:
            return OrchestratorResult(answer="", no_tools=True)

        tool_defs = self._injector.inject(visible)
        bound = self._llm.bind_tools(tool_defs)
        if context:
            system = _SYSTEM_PROMPT_WITH_CONTEXT.replace("{context}", context)
        else:
            system = _SYSTEM_PROMPT
        messages: list[Any] = [
            {"role": "system", "content": system},
            *(history or []),
            {"role": "user", "content": query},
        ]

        tool_calls_log: list[ToolCallRecord] = []
        max_rounds = self._settings.max_tool_rounds
        for round_idx in range(max_rounds):
            if on_token is not None and hasattr(bound, "astream"):
                # 流式收集本轮响应, 聚合后判断是否工具调用
                chunks: list[Any] = []
                async for chunk in bound.astream(messages):
                    chunks.append(chunk)
                response: Any = chunks[0] if chunks else None
                for c in chunks[1:]:
                    response = response + c
            else:
                response = await bound.ainvoke(messages)
            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                # 无工具调用: 本轮即最终答案; 流式路径把收集到的文本逐段回传
                if on_token is not None and hasattr(bound, "astream"):
                    for c in chunks:
                        text = self._extract_text(c)
                        if text:
                            await on_token(text)
                    answer = self._extract_text(response)
                else:
                    answer = getattr(response, "content", "") or str(response)
                    if on_token is not None:
                        await on_token(answer)
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
                if on_tool is not None:
                    await on_tool(record)
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

    @staticmethod
    def _extract_text(obj: Any) -> str:
        """从 langchain chunk/消息/str 提取文本增量(流式收集用)."""
        if isinstance(obj, str):
            return obj
        content = getattr(obj, "content", None)
        return str(content) if content is not None else ""

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
        # 文件类工具自动补 session_id(LLM 未提供时), 便于沙盒会话隔离
        if session_id is not None:
            args.setdefault("session_id", session_id)
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
