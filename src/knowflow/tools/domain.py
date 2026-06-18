"""执行域管理 - 域可见性规则与 Agent 角色定义.

四类执行域(对齐 core/constants.py ExecutionDomain)的可见性规则:
- direct: 主/子 Agent 始终可见
- skill_only: Skill 激活后注入(主/子均可见)
- subagent_only: 仅子 Agent 可见
- internal: 永不暴露给模型
"""

from enum import StrEnum

from knowflow.core.constants import ExecutionDomain

# 主 Agent 可见域(direct 始终 + skill_only 按激活)
MAIN_VISIBLE_DOMAINS: frozenset[ExecutionDomain] = frozenset(
    {ExecutionDomain.DIRECT, ExecutionDomain.SKILL_ONLY}
)
# 子 Agent 可见域(额外含 subagent_only)
SUBAGENT_VISIBLE_DOMAINS: frozenset[ExecutionDomain] = frozenset(
    {ExecutionDomain.DIRECT, ExecutionDomain.SKILL_ONLY, ExecutionDomain.SUBAGENT_ONLY}
)
# 永不注入给模型的域
HIDDEN_DOMAINS: frozenset[ExecutionDomain] = frozenset({ExecutionDomain.INTERNAL})


class AgentRole(StrEnum):
    """Agent 角色. 决定 subagent_only 域是否可见."""

    MAIN = "main"
    SUBAGENT = "subagent"


def visible_domains_for(role: AgentRole) -> frozenset[ExecutionDomain]:
    """返回该角色可见的执行域集合(不含 internal)."""
    return SUBAGENT_VISIBLE_DOMAINS if role == AgentRole.SUBAGENT else MAIN_VISIBLE_DOMAINS


def filter_skills_by_role(skills: list, role: AgentRole) -> list:
    """按角色过滤可激活的 Skill.

    subagent_only 域的 Skill 仅子 Agent 可激活; 其余域(skill_only/direct)主子均可.
    用于在可见性计算前剔除当前角色不应激活的 Skill.
    """
    return [
        s
        for s in skills
        if s.enabled and (s.domain != ExecutionDomain.SUBAGENT_ONLY or role == AgentRole.SUBAGENT)
    ]
