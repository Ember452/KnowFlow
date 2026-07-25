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
    subtask_id: str | None = None  # 子 Agent 场景标注来源子任务(主链路为 None)


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

    def visible_tools_text(self, agent_role: AgentRole = AgentRole.SUBAGENT) -> str:
        """返回指定角色可见工具清单文本(供主 Agent 规划 prompt 注入).

        子 Agent 执行前需知道可调用的工具集, 主 Agent 据此拆出"能被执行"的任务.
        """
        active = filter_skills_by_role(self._skills.active_skills(), agent_role)
        visible = self._visibility.compute(active, agent_role, self._registry)
        if not visible:
            return "(无可用工具)"
        return "; ".join(f"{t.name}({t.description})" for t in visible)

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
        system_prompt: str | None = None,
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
            system_prompt: 自定义系统提示(如子 Agent 任务型 prompt); None 时用默认提示,
                非 None 时优先使用且不再拼接 context(调用方自行拼好).
        """
        # ---- 第 1 步: 确定激活 Skill 集 ----
        # 调用方未指定 active_skills 时, 取 SkillManager 中全部启用项;
        # 无论来源如何, 都按当前 Agent 角色过滤(subagent_only 域对主 Agent 不可见).
        if active_skills is None:
            active = filter_skills_by_role(self._skills.active_skills(), agent_role)
        else:
            active = filter_skills_by_role(active_skills, agent_role)

        # ---- 第 2 步: 计算可见工具 ----
        # VisibilityCalculator 依据激活 Skill + 角色 + 注册表计算本轮可注入的工具集,
        # 完成执行域隔离(权限边界在第 4 步 Invoke 前还会逐次校验).
        visible = self._visibility.compute(active, agent_role, self._registry)
        if not visible:
            # 无可见工具: 直接短路返回, 明确标记 no_tools, 上层据此决定兜底策略
            return OrchestratorResult(answer="", no_tools=True)

        # ---- 第 3 步: 注入工具并组装首轮消息 ----
        # Injector 把 Skill 定义转换成 OpenAI 风格 tool 描述(每个 Skill 一个工具),
        # bind_tools 绑定到 LLM, 使模型在响应中能输出 tool_calls.
        tool_defs = self._injector.inject(visible)
        bound = self._llm.bind_tools(tool_defs)
        # 上层预检索过(chat_service)时, 把检索上下文注入 system prompt,
        # 避免模型重复调用检索工具(上下文取配置中 max_retrieve_context_chars 截断).
        if system_prompt is not None:
            system = system_prompt
        elif context:
            system = _SYSTEM_PROMPT_WITH_CONTEXT.replace("{context}", context)
        else:
            system = _SYSTEM_PROMPT
        # 消息结构: [system, *(history), user]; 历史原样透传, 不裁剪
        messages: list[Any] = [
            {"role": "system", "content": system},
            *(history or []),
            {"role": "user", "content": query},
        ]

        # ---- 第 4 步: 工具调用循环 ----
        # 每轮先让 LLM 生成响应; 若有 tool_calls 则执行并回填 tool 消息, 进入下一轮;
        # 直到 LLM 不再调用工具(给出最终答案)或耗尽 max_tool_rounds.
        tool_calls_log: list[ToolCallRecord] = []
        max_rounds = self._settings.max_tool_rounds
        for round_idx in range(max_rounds):
            # 流式路径: 调用方要求逐段回传且 LLM 支持 astream 时走流式;
            # 把每轮全部分块用 + 聚合为一条完整响应, 供后续统一判断工具调用.
            if on_token is not None and hasattr(bound, "astream"):
                chunks: list[Any] = []
                async for chunk in bound.astream(messages):
                    chunks.append(chunk)
                response: Any = chunks[0] if chunks else None
                for c in chunks[1:]:
                    response = response + c
            else:
                # 非流式路径: 一次性等待完整响应
                response = await bound.ainvoke(messages)
            # tool_calls 为空即本轮不再调用工具, 可安全结束循环
            calls = getattr(response, "tool_calls", None) or []
            if not calls:
                # 无工具调用: 本轮响应即最终答案
                if on_token is not None and hasattr(bound, "astream"):
                    # 流式路径: 把各分片中的文本增量逐段回传调用方(边生成边展示),
                    # 再从聚合响应中提取完整答案用于返回.
                    for c in chunks:
                        text = self._extract_text(c)
                        if text:
                            await on_token(text)
                    answer = self._extract_text(response)
                else:
                    # 非流式路径: 直接取 content(缺失时兜底取 str 表示), 一次性回传
                    answer = getattr(response, "content", "") or str(response)
                    if on_token is not None:
                        await on_token(answer)
                return OrchestratorResult(
                    answer=answer,
                    tool_calls=tool_calls_log,
                    rounds=round_idx,  # rounds 记录实际用掉的轮数
                )
            # 本轮有工具调用: 先把含 tool_calls 的 assistant 消息整体回填,
            # 下轮模型才能借助这些调用意图关联后续的 tool 结果.
            messages.append(response)
            for tc in calls:
                # 执行单个工具调用(权限校验/执行/指标记录在 _invoke_tool 内完成)
                record = await self._invoke_tool(tc, agent_role, active, session_id)
                tool_calls_log.append(record)
                if on_tool is not None:
                    # 每次调用完成后通知上层(事件流展示用)
                    await on_tool(record)
                # 工具结果以 role=tool 消息回填(tool_call_id 与 assistant 消息的
                # tool_calls 一一对应; 成功写 output, 失败写 error 文本, 不让异常中断循环).
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tc.get("id", "")),
                        "name": record.tool_name,
                        "content": str(record.output if record.success else record.error),
                    }
                )

        # ---- 第 5 步: 超过最大轮数 ----
        # 循环自然结束说明 LLM 一直未给出最终答案; 记录告警并以占位答案返回,
        # truncated=True 让上层知道结果不完整, 可选择提示用户或拼接已有内容.
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
