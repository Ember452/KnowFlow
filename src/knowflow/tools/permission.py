"""工具权限校验 - 运行时越权拦截.

check(tool_name, agent_role, active_skills, registry): 执行工具前校验该工具在当前
上下文是否可见. 不可见则拦截 + 抛 ToolExecutionError(越权), 供 trace 记录.
防止模型被注入后绕过执行域直接调用 subagent_only/internal 工具.
"""

from knowflow.core.exceptions import ToolExecutionError
from knowflow.tools.domain import AgentRole
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition
from knowflow.tools.visibility import VisibilityCalculator


class PermissionChecker:
    """运行时工具权限校验."""

    def __init__(self, visibility: VisibilityCalculator | None = None) -> None:
        self._visibility = visibility or VisibilityCalculator()

    def check(
        self,
        tool_name: str,
        agent_role: AgentRole,
        active_skills: list[SkillDefinition],
        registry: ToolRegistry,
    ) -> None:
        """校验工具在当前上下文可见; 越权抛 ToolExecutionError."""
        if not registry.has(tool_name):
            raise ToolExecutionError(
                f"工具未注册: {tool_name}",
                details={"tool": tool_name},
            )
        visible = self._visibility.compute(active_skills, agent_role, registry)
        visible_names = {t.name for t in visible}
        if tool_name not in visible_names:
            raise ToolExecutionError(
                f"工具越权调用: {tool_name} 在当前执行域不可见",
                details={
                    "tool": tool_name,
                    "agent_role": agent_role.value,
                    "visible_tools": sorted(visible_names),
                },
            )
