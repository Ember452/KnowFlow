"""依赖解析器单测 - 拓扑排序/传递依赖/循环检测/缺失依赖校验.

resolve(skill, registry) 返回 skill 所需工具(含传递依赖)的拓扑有序列表.
"""

from typing import Any

import pytest

from knowflow.core.constants import ExecutionDomain
from knowflow.core.exceptions import ValidationError
from knowflow.tools.base import BaseTool, ToolResult
from knowflow.tools.dependency_resolver import DependencyResolver
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition


class _Tool(BaseTool):
    def __init__(self, name: str, requires: tuple[str, ...] = ()) -> None:
        self.name = name
        self.requires = requires
        self.domain = ExecutionDomain.SKILL_ONLY
        self.description = name

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(tool_name=self.name)


def _build_registry(*tools: _Tool) -> ToolRegistry:
    reg = ToolRegistry()
    for t in tools:
        reg.register(t)
    return reg


# ── 基础解析 ──


def test_resolve_simple_tools() -> None:
    """无依赖的工具按 skill.tools 顺序返回."""
    reg = _build_registry(_Tool("a"), _Tool("b"))
    skill = SkillDefinition(name="s", tools=["a", "b"])
    assert DependencyResolver().resolve(skill, reg) == ["a", "b"]


def test_resolve_includes_dependencies() -> None:
    """dependencies 与 tools 合并, 去重."""
    reg = _build_registry(_Tool("a"), _Tool("b"), _Tool("c"))
    skill = SkillDefinition(name="s", tools=["a"], dependencies=["b", "c"])
    result = DependencyResolver().resolve(skill, reg)
    assert set(result) == {"a", "b", "c"}


def test_resolve_empty() -> None:
    """无 tools 也无 dependencies 返回空."""
    reg = _build_registry(_Tool("a"))
    skill = SkillDefinition(name="s", tools=[], dependencies=[])
    assert DependencyResolver().resolve(skill, reg) == []


# ── 传递依赖与拓扑排序 ──


def test_resolve_transitive_requires() -> None:
    """展开工具的 requires 传递依赖, 拓扑序: 被依赖者在前."""
    # c 依赖 b, b 依赖 a → 拓扑序 a, b, c
    reg = _build_registry(_Tool("a"), _Tool("b", requires=("a",)), _Tool("c", requires=("b",)))
    skill = SkillDefinition(name="s", tools=["c"])
    result = DependencyResolver().resolve(skill, reg)
    assert result == ["a", "b", "c"]


def test_resolve_topological_order() -> None:
    """多分支依赖的拓扑序: 被依赖项先输出."""
    # d 依赖 a 和 c, c 依赖 b → b, c 在 d 前; a 在 d 前
    reg = _build_registry(
        _Tool("a"),
        _Tool("b"),
        _Tool("c", requires=("b",)),
        _Tool("d", requires=("a", "c")),
    )
    skill = SkillDefinition(name="s", tools=["d"])
    result = DependencyResolver().resolve(skill, reg)
    # d 必须在最后, b 必须在 c 前
    assert result[-1] == "d"
    assert result.index("b") < result.index("c")


# ── 异常路径 ──


def test_resolve_missing_tool_raises() -> None:
    """skill 引用未注册工具抛 ValidationError."""
    reg = _build_registry(_Tool("a"))
    skill = SkillDefinition(name="s", tools=["a", "missing"])
    with pytest.raises(ValidationError, match="未注册"):
        DependencyResolver().resolve(skill, reg)


def test_resolve_missing_transitive_dependency_raises() -> None:
    """工具的 requires 引用未注册工具抛 ValidationError."""
    reg = _build_registry(_Tool("a", requires=("ghost",)))
    skill = SkillDefinition(name="s", tools=["a"])
    with pytest.raises(ValidationError, match="未注册"):
        DependencyResolver().resolve(skill, reg)


def test_resolve_cycle_detected() -> None:
    """循环依赖抛 ValidationError, 错误信息含环路径."""
    # a 依赖 b, b 依赖 a → 循环
    reg = _build_registry(_Tool("a", requires=("b",)), _Tool("b", requires=("a",)))
    skill = SkillDefinition(name="s", tools=["a"])
    with pytest.raises(ValidationError, match="循环依赖"):
        DependencyResolver().resolve(skill, reg)


def test_resolve_self_cycle_detected() -> None:
    """自环依赖(a 依赖 a)被检测."""
    reg = _build_registry(_Tool("a", requires=("a",)))
    skill = SkillDefinition(name="s", tools=["a"])
    with pytest.raises(ValidationError, match="循环依赖"):
        DependencyResolver().resolve(skill, reg)
