"""工具权限校验单测 - 运行时越权拦截.

check(): 工具在当前上下文不可见时抛 ToolExecutionError. 防止模型绕过执行域调用
subagent_only/internal 工具, 或调用未激活的 skill_only 工具.
"""

from typing import Any

import pytest

from knowflow.core.constants import ExecutionDomain
from knowflow.core.exceptions import ToolExecutionError
from knowflow.tools.base import BaseTool, ToolResult
from knowflow.tools.domain import AgentRole
from knowflow.tools.permission import PermissionChecker
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition


class _Tool(BaseTool):
    def __init__(self, name: str, domain: ExecutionDomain) -> None:
        self.name = name
        self.domain = domain
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


def _skill(tools: list[str]) -> list[SkillDefinition]:
    return [SkillDefinition(name="s", tools=tools, enabled=True)]


# ── 可见工具通过校验 ──


def test_check_direct_visible_passes() -> None:
    """direct 工具对主 Agent 可见, 校验通过."""
    reg = _build_registry(_Tool("calc", ExecutionDomain.DIRECT))
    PermissionChecker().check("calc", AgentRole.MAIN, [], reg)  # 不抛即通过


def test_check_skill_only_with_activation_passes() -> None:
    """skill_only 工具被激活 Skill 引用时校验通过."""
    reg = _build_registry(_Tool("file", ExecutionDomain.SKILL_ONLY))
    PermissionChecker().check("file", AgentRole.MAIN, _skill(["file"]), reg)


def test_check_subagent_tool_for_subagent_passes() -> None:
    """subagent_only 工具对子 Agent 校验通过."""
    reg = _build_registry(_Tool("search", ExecutionDomain.SUBAGENT_ONLY))
    PermissionChecker().check("search", AgentRole.SUBAGENT, [], reg)


# ── 越权拦截 ──


def test_check_unregistered_raises() -> None:
    """未注册工具抛 ToolExecutionError."""
    reg = _build_registry(_Tool("calc", ExecutionDomain.DIRECT))
    with pytest.raises(ToolExecutionError, match="未注册"):
        PermissionChecker().check("ghost", AgentRole.MAIN, [], reg)


def test_check_subagent_tool_for_main_raises() -> None:
    """主 Agent 调用 subagent_only 工具被拦截."""
    reg = _build_registry(_Tool("search", ExecutionDomain.SUBAGENT_ONLY))
    with pytest.raises(ToolExecutionError, match="越权"):
        PermissionChecker().check("search", AgentRole.MAIN, [], reg)


def test_check_internal_tool_raises() -> None:
    """internal 工具任何角色都不可调用."""
    reg = _build_registry(_Tool("secret", ExecutionDomain.INTERNAL))
    with pytest.raises(ToolExecutionError, match="越权"):
        PermissionChecker().check("secret", AgentRole.MAIN, [], reg)
    with pytest.raises(ToolExecutionError, match="越权"):
        PermissionChecker().check("secret", AgentRole.SUBAGENT, [], reg)


def test_check_skill_only_without_activation_raises() -> None:
    """skill_only 工具无 Skill 激活时被拦截."""
    reg = _build_registry(_Tool("file", ExecutionDomain.SKILL_ONLY))
    with pytest.raises(ToolExecutionError, match="越权"):
        PermissionChecker().check("file", AgentRole.MAIN, [], reg)
