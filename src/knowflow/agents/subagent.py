"""Subagent - 独立上下文执行委派任务.

与主 Agent 上下文隔离: 只看到自己的子任务 + 共享的预检索上下文,
不注入主 Agent 的完整对话历史. 可选注入独立 ContextManager 实例
(窗口/预算策略与主 Agent 互不影响), 缺省用内置 prompt 组装.
"""

from typing import Any

from knowflow.agents.base import BaseAgent
from knowflow.agents.prompts import SUBAGENT_SYSTEM_PROMPT_TEMPLATE
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


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
    ) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake.
            settings: Settings 单例.
            context_manager: 独立 ContextManager 实例(子 Agent 上下文策略),
                None 时用内置 prompt 组装.
        """
        super().__init__(llm, settings)
        self._context_manager = context_manager

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
    ) -> dict[str, Any]:
        """执行委派任务, 返回 {"output": str}.

        Args:
            task: 子任务描述(主 Agent 规划产出, 完整自包含).
            retrieval_context: 共享预检索上下文文本(主 Agent 预检索注入).
            session_id: 会话 id(上下文策略用).
        """
        messages = await self._build_messages(task, retrieval_context, session_id)
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
