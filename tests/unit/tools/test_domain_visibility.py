"""执行域与可见性计算单测 - 域可见性规则/Skill 过滤/可见工具集计算.

核心验证"执行域隔离"逻辑:
- direct 恒可见(主/子)
- skill_only 仅 Skill 激活后可见
- subagent_only 仅子 Agent 可见
- internal 永不可见
"""

from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.base import BaseTool, ToolResult
from knowflow.tools.domain import (
    HIDDEN_DOMAINS,
    MAIN_VISIBLE_DOMAINS,
    SUBAGENT_VISIBLE_DOMAINS,
    AgentRole,
    filter_skills_by_role,
    visible_domains_for,
)
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition
from knowflow.tools.visibility import VisibilityCalculator


class _Tool(BaseTool):
    """测试用工具桩."""

    def __init__(self, name: str, domain: ExecutionDomain) -> None:
        self.name = name
        self.domain = domain
        self.description = name

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(tool_name=self.name)


def _skill(
    name: str,
    tools: list[str],
    domain: ExecutionDomain = ExecutionDomain.SKILL_ONLY,
) -> SkillDefinition:
    return SkillDefinition(name=name, tools=tools, domain=domain, enabled=True)


# ── 执行域常量 ──


def test_domain_sets() -> None:
    """主 Agent 可见 direct+skill_only; 子 Agent 额外含 subagent_only; internal 永隐藏."""
    assert frozenset({ExecutionDomain.DIRECT, ExecutionDomain.SKILL_ONLY}) == MAIN_VISIBLE_DOMAINS
    assert (
        frozenset(
            {ExecutionDomain.DIRECT, ExecutionDomain.SKILL_ONLY, ExecutionDomain.SUBAGENT_ONLY}
        )
        == SUBAGENT_VISIBLE_DOMAINS
    )
    assert frozenset({ExecutionDomain.INTERNAL}) == HIDDEN_DOMAINS


def test_visible_domains_for_main_and_subagent() -> None:
    """visible_domains_for 按角色返回可见域集合."""
    assert visible_domains_for(AgentRole.MAIN) == MAIN_VISIBLE_DOMAINS
    assert visible_domains_for(AgentRole.SUBAGENT) == SUBAGENT_VISIBLE_DOMAINS


# ── filter_skills_by_role ──


def test_filter_skills_main_excludes_subagent_only() -> None:
    """主 Agent 过滤掉 subagent_only 域的 Skill."""
    skills = [
        _skill("qa", ["retrieval_tool"], ExecutionDomain.SKILL_ONLY),
        _skill("expert", ["search_tool"], ExecutionDomain.SUBAGENT_ONLY),
    ]
    assert [s.name for s in filter_skills_by_role(skills, AgentRole.MAIN)] == ["qa"]


def test_filter_skills_subagent_includes_all() -> None:
    """子 Agent 可激活全部域(含 subagent_only)的 Skill."""
    skills = [
        _skill("qa", ["retrieval_tool"], ExecutionDomain.SKILL_ONLY),
        _skill("expert", ["search_tool"], ExecutionDomain.SUBAGENT_ONLY),
    ]
    assert [s.name for s in filter_skills_by_role(skills, AgentRole.SUBAGENT)] == ["qa", "expert"]


def test_filter_skills_excludes_disabled() -> None:
    """disabled 的 Skill 被过滤."""
    skills = [
        SkillDefinition(name="on", tools=["a"], enabled=True),
        SkillDefinition(name="off", tools=["b"], enabled=False),
    ]
    assert [s.name for s in filter_skills_by_role(skills, AgentRole.MAIN)] == ["on"]


# ── VisibilityCalculator.compute ──


def test_compute_direct_always_visible() -> None:
    """direct 域工具无需 Skill 激活即对主/子 Agent 可见."""
    reg = ToolRegistry()
    reg.register(_Tool("calc", ExecutionDomain.DIRECT))
    visible = VisibilityCalculator().compute([], AgentRole.MAIN, reg)
    assert [t.name for t in visible] == ["calc"]


def test_compute_skill_only_requires_activation() -> None:
    """skill_only 工具: 无 Skill 激活时不可见, 激活后可见."""
    reg = ToolRegistry()
    reg.register(_Tool("file_read", ExecutionDomain.SKILL_ONLY))
    calc = VisibilityCalculator()
    # 无激活 Skill
    assert calc.compute([], AgentRole.MAIN, reg) == []
    # 激活引用该工具的 Skill
    skills = [_skill("data_analysis", ["file_read"])]
    visible = calc.compute(skills, AgentRole.MAIN, reg)
    assert [t.name for t in visible] == ["file_read"]


def test_compute_subagent_only_only_for_subagent() -> None:
    """subagent_only 工具: 主 Agent 不可见, 子 Agent 可见."""
    reg = ToolRegistry()
    reg.register(_Tool("search", ExecutionDomain.SUBAGENT_ONLY))
    calc = VisibilityCalculator()
    assert calc.compute([], AgentRole.MAIN, reg) == []
    assert [t.name for t in calc.compute([], AgentRole.SUBAGENT, reg)] == ["search"]


def test_compute_internal_never_visible() -> None:
    """internal 域工具永不可见."""
    reg = ToolRegistry()
    reg.register(_Tool("secret", ExecutionDomain.INTERNAL))
    calc = VisibilityCalculator()
    assert calc.compute([], AgentRole.MAIN, reg) == []
    assert calc.compute([], AgentRole.SUBAGENT, reg) == []


def test_compute_dedup_and_order() -> None:
    """多个 Skill 引用同一工具时去重, 按注册顺序输出."""
    reg = ToolRegistry()
    reg.register(_Tool("a", ExecutionDomain.SKILL_ONLY))
    reg.register(_Tool("b", ExecutionDomain.SKILL_ONLY))
    calc = VisibilityCalculator()
    skills = [
        _skill("s1", ["a", "b"]),
        _skill("s2", ["a"]),  # a 被重复引用
    ]
    visible = calc.compute(skills, AgentRole.MAIN, reg)
    assert [t.name for t in visible] == ["a", "b"]


def test_compute_dependencies_activate_tools() -> None:
    """Skill 的 dependencies 也能激活 skill_only 工具."""
    reg = ToolRegistry()
    reg.register(_Tool("helper", ExecutionDomain.SKILL_ONLY))
    calc = VisibilityCalculator()
    skills = [SkillDefinition(name="s", tools=[], dependencies=["helper"])]
    visible = calc.compute(skills, AgentRole.MAIN, reg)
    assert [t.name for t in visible] == ["helper"]


def test_compute_mixed_domains_main() -> None:
    """主 Agent: direct 可见 + skill_only(激活) 可见, subagent/internal 不可见."""
    reg = ToolRegistry()
    reg.register(_Tool("calc", ExecutionDomain.DIRECT))
    reg.register(_Tool("file", ExecutionDomain.SKILL_ONLY))
    reg.register(_Tool("search", ExecutionDomain.SUBAGENT_ONLY))
    reg.register(_Tool("secret", ExecutionDomain.INTERNAL))
    calc = VisibilityCalculator()
    skills = [_skill("data", ["file"])]
    visible = calc.compute(skills, AgentRole.MAIN, reg)
    assert {t.name for t in visible} == {"calc", "file"}
