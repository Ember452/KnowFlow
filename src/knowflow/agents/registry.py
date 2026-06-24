"""Agent 注册表 - 主/子 Agent 元信息注册与查询.

P8 只注册 main/sub 两个 Agent; 注册表提供统一入口, 便于后续扩展更多角色
(如 reviewer/planner), 与工具注册表设计一致.
"""

from __future__ import annotations

from knowflow.agents.base import BaseAgent
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


class AgentRegistry:
    """Agent 注册表."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """注册 Agent(同名覆盖并告警)."""
        if agent.name in self._agents:
            logger.warning("agent_registry.overwrite", name=agent.name)
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        """按注册名取 Agent."""
        return self._agents.get(name)

    def list_all(self) -> list[BaseAgent]:
        """全部已注册 Agent(按注册名排序)."""
        return [self._agents[name] for name in sorted(self._agents)]

    def names(self) -> list[str]:
        """已注册 Agent 名称."""
        return sorted(self._agents)
