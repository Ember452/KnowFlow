"""可见性计算 - 根据激活 Skill + Agent 角色, 计算模型可见工具集.

compute(active_skills, agent_role, registry) → list[ToolDef]:
- direct 域恒可见
- skill_only 域: 仅当所属 Skill 激活时可见(通过 Skill 的 tools 列表判定)
- subagent_only 域: 仅当 agent_role == SUBAGENT 时可见
- internal 域: 永不可见

输出用于构建 LLM tools 参数, 是"执行域隔离"指标的核心.
"""

from knowflow.tools.base import ToolDef
from knowflow.tools.domain import HIDDEN_DOMAINS, AgentRole, visible_domains_for
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition


class VisibilityCalculator:
    """计算模型可见工具集."""

    def compute(
        self,
        active_skills: list[SkillDefinition],
        agent_role: AgentRole,
        registry: ToolRegistry,
    ) -> list[ToolDef]:
        """返回可见工具的 ToolDef 列表(按注册顺序, 去重)."""
        # 激活 Skill 显式声明的工具集合(skill_only 工具通过此途径可见)
        skill_tool_names: set[str] = set()
        for skill in active_skills:
            if not skill.enabled:
                continue
            skill_tool_names.update(skill.tools)
            skill_tool_names.update(skill.dependencies)

        visible_domains = visible_domains_for(agent_role)
        result: list[ToolDef] = []
        seen: set[str] = set()
        for tool in registry.list_all():
            if tool.domain in HIDDEN_DOMAINS:
                continue
            if not self._is_visible(tool.domain, tool.name, visible_domains, skill_tool_names):
                continue
            if tool.name in seen:
                continue
            seen.add(tool.name)
            result.append(tool.to_def())
        return result

    @staticmethod
    def _is_visible(
        domain: object,
        tool_name: str,
        visible_domains: frozenset,
        skill_tool_names: set[str],
    ) -> bool:
        """判定单个工具是否可见.

        skill_only 工具需同时满足: 域在可见集合中 且 被某激活 Skill 引用.
        direct/subagent_only 仅看域集合.
        """
        from knowflow.core.constants import ExecutionDomain

        if domain not in visible_domains:
            return False
        if domain == ExecutionDomain.SKILL_ONLY:
            return tool_name in skill_tool_names
        return True
