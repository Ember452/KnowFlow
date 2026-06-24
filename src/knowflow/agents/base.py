"""BaseAgent 抽象 - decide/act/observe 三步决策循环.

主/子 Agent 都遵循同一抽象: decide(决定下一步动作) → act(执行动作) →
observe(观察结果并更新状态). 具体动作由子类实现(MainAgent 规划/委派/汇总,
Subagent 执行委派任务), 上层(LangGraph 节点)只依赖 BaseAgent 接口.
"""

from abc import ABC, abstractmethod
from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Agent 基类.

    Attributes:
        name: Agent 注册名(registry 用).
        role: 执行域角色(main/sub), 决定 subagent_only 工具可见性.
        description: 注册表展示用描述.
    """

    name: str = "base"
    role: str = "main"
    description: str = ""

    def __init__(self, llm: Any | None = None, settings: Settings | None = None) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake(实现 ainvoke). None 时懒加载单例.
            settings: Settings 单例.
        """
        self._llm: Any | None = llm
        self._settings = settings or get_settings()

    def _get_llm(self) -> Any:
        """取 LLM: 优先注入实例, 否则懒加载全局单例."""
        if self._llm is not None:
            return self._llm
        from knowflow.core.llm import get_chat_llm

        return get_chat_llm()

    @abstractmethod
    async def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        """决定下一步动作. 返回状态更新 dict(如 {"action": "delegate"})."""

    @abstractmethod
    async def act(self, state: dict[str, Any]) -> dict[str, Any]:
        """执行动作. 返回状态更新 dict(如 {"plan": [...]})."""

    @abstractmethod
    async def observe(self, state: dict[str, Any]) -> dict[str, Any]:
        """观察执行结果, 更新状态. 返回状态更新 dict(如 {"final_answer": "..."})."""
