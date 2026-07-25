"""Subagent - 独立上下文执行委派任务.

与主 Agent 上下文隔离: 只看到自己的子任务 + 共享的预检索上下文,
不注入主 Agent 的完整对话历史. 可选注入独立 ContextManager 实例
(窗口/预算策略与主 Agent 互不影响), 缺省用内置 prompt 组装.
"""

from typing import Any

from knowflow.agents.base import BaseAgent
from knowflow.agents.prompts import SUBAGENT_SYSTEM_PROMPT_TEMPLATE, SUBAGENT_TOOL_PROMPT_TEMPLATE
from knowflow.core.logging import get_logger
from knowflow.tools.domain import AgentRole

logger = get_logger(__name__)

# 子 Agent 输出质量门禁阈值: 低于该长度视为无效输出(触发重试)
_MIN_OUTPUT_CHARS = 20


def quality_check(output: str, min_chars: int = _MIN_OUTPUT_CHARS) -> tuple[bool, str]:
    """子 Agent 输出质量门禁: 空/过短视为无效, 返回 (是否通过, 原因).

    供 orchestrator 重试判定使用: 未通过时携带原因重试一次,
    避免无效结果(空输出/截断)直接进入汇总污染最终答案.
    """
    text = (output or "").strip()
    if not text:
        return False, "输出为空"
    if len(text) < min_chars:
        return False, f"输出过短({len(text)} 字符 < {min_chars})"
    return True, ""


class Subagent(BaseAgent):
    """子 Agent: 独立上下文执行委派任务."""

    name = "sub"
    role = "sub"
    description = "子 Agent: 独立上下文执行委派任务"

    def __init__(
        self,
        llm: Any | None = None,
        settings: Any | None = None,
        context_manager: Any | None = None,
        tool_orchestrator: Any | None = None,
    ) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake.
            settings: Settings 单例.
            context_manager: 独立 ContextManager 实例(子 Agent 上下文策略),
                None 时用内置 prompt 组装.
            tool_orchestrator: ToolOrchestrator(实现 async run); 注入后子 Agent
                以 SUBAGENT 角色跑工具循环(subagent_only 域可见), None 时纯 LLM 执行.
        """
        super().__init__(llm, settings)
        self._context_manager = context_manager
        self._tool_orchestrator = tool_orchestrator

    # ── BaseAgent 三步循环 ──

    async def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        """子 Agent 直接执行委派任务."""
        return {"action": "execute"}

    async def act(self, state: dict[str, Any]) -> dict[str, Any]:
        """执行任务: 独立上下文 → LLM 生成 → 输出."""
        task = state.get("task", "")
        context = state.get("retrieval_context", "")
        messages = await self._build_messages(task, context, state.get("session_id"))
        response = await self._get_llm().ainvoke(messages)
        output = _extract_text(response).strip()
        return {"output": output}

    async def observe(self, state: dict[str, Any]) -> dict[str, Any]:
        """返回执行结果."""
        return {"output": state.get("output", "")}

    # ── 子 Agent 核心方法 ──

    async def execute(
        self,
        task: str,
        retrieval_context: str = "",
        session_id: int | None = None,
        retry_hint: str | None = None,
        on_tool: Any | None = None,
    ) -> dict[str, Any]:
        """执行委派任务, 返回 {"output": str, "tool_calls": [...]}.

        Args:
            task: 子任务描述(主 Agent 规划产出, 完整自包含).
            retrieval_context: 检索上下文(按需检索结果或共享预检索上下文).
            session_id: 会话 id(上下文策略/文件工具会话隔离用).
            retry_hint: 重试提示(上次失败原因/质量门禁未通过原因).
            on_tool: 可选回调, 子 Agent 每次工具调用完成后通知调用方(SSE 展示用).

        注入 tool_orchestrator 时走工具循环(SUBAGENT 角色, subagent_only 域可见);
        未注入时回退纯 LLM 组装路径(测试/降级, 行为不变).
        """
        if self._tool_orchestrator is not None:
            # 工具循环路径: retry_hint 拼入任务描述(无独立消息通道), 系统提示声明
            # 可用工具集 + 检索上下文, 由编排器组装工具消息并循环执行.
            if retry_hint:
                task = f"{task}\n\n[上次执行反馈] {retry_hint}"
            context_section = f"检索上下文:\n{retrieval_context}" if retrieval_context else ""
            system = SUBAGENT_TOOL_PROMPT_TEMPLATE.format(
                available_tools=self._tool_orchestrator.visible_tools_text(AgentRole.SUBAGENT),
                context_section=context_section,
            )
            result = await self._tool_orchestrator.run(
                task,
                session_id=str(session_id) if session_id is not None else None,
                agent_role=AgentRole.SUBAGENT,
                on_tool=on_tool,
                system_prompt=system,
            )
            tool_calls = [
                {
                    "tool_name": tc.tool_name,
                    "args": tc.args,
                    "success": tc.success,
                    "latency_ms": tc.latency_ms,
                    "error": tc.error,
                }
                for tc in result.tool_calls
            ]
            output = (result.answer or "").strip()
            logger.info(
                "subagent.executed", task=task[:80], chars=len(output), tools=len(tool_calls)
            )
            return {"output": output, "tool_calls": tool_calls}
        messages = await self._build_messages(task, retrieval_context, session_id)
        if retry_hint:
            messages.append({"role": "user", "content": f"[上次执行反馈] {retry_hint}"})
        response = await self._get_llm().ainvoke(messages)
        output = _extract_text(response).strip()
        logger.info("subagent.executed", task=task[:80], chars=len(output))
        return {"output": output}

    async def _build_messages(
        self, task: str, retrieval_context: str, session_id: int | None
    ) -> list[dict[str, Any]]:
        """组装子 Agent 消息: 优先独立 ContextManager, 否则内置组装."""
        if self._context_manager is not None:
            ctx = await self._context_manager.build(
                task,
                [],
                session_id=session_id,
                retrieval=retrieval_context or None,
            )
            return list(ctx.messages)
        context_section = f"检索上下文:\n{retrieval_context}" if retrieval_context else ""
        system = SUBAGENT_SYSTEM_PROMPT_TEMPLATE.format(context_section=context_section)
        return [{"role": "system", "content": system}, {"role": "user", "content": task}]


def _extract_text(obj: Any) -> str:
    """从 LLM 响应提取文本: 兼容 str 与 langchain 消息对象."""
    if isinstance(obj, str):
        return obj
    content = getattr(obj, "content", None)
    return str(content) if content is not None else ""
