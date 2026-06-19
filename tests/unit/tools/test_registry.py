"""工具注册表与基类单测 - 注册/查询/按域过滤/ToolDef 转换.

校验 ToolRegistry 的注册唯一性、按域过滤、批量查询, 以及 BaseTool.to_def 的扁平化.
"""

from typing import Any

import pytest

from knowflow.core.constants import ExecutionDomain
from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.tools.base import BaseTool, ToolDef, ToolResult
from knowflow.tools.registry import ToolRegistry


class _FakeTool(BaseTool):
    """测试用工具桩: 可配置 name/domain/requires."""

    def __init__(
        self,
        name: str,
        domain: ExecutionDomain = ExecutionDomain.SKILL_ONLY,
        requires: tuple[str, ...] = (),
        description: str = "fake",
    ) -> None:
        self.name = name
        self.domain = domain
        self.requires = requires
        self.description = description

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"x": {"type": "string"}}}

    async def execute(self, **kwargs: Any) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True, output=kwargs)


# ── ToolDef ──


def test_tooldef_schema_size_chars() -> None:
    """schema_size_chars 返回 input_schema 的 JSON 字符数."""
    d = ToolDef(
        name="t",
        description="d",
        domain=ExecutionDomain.DIRECT,
        input_schema={"type": "object", "properties": {"a": {"type": "string"}}},
    )
    assert d.schema_size_chars() > 0
    # 空 schema 字符数为 "{}" 的长度
    assert ToolDef(name="e", description="", domain=ExecutionDomain.DIRECT).schema_size_chars() == 2


def test_basetool_to_def_flattens() -> None:
    """to_def 将工具扁平化为 ToolDef, 保留 name/domain/requires/schema."""
    tool = _FakeTool("calc", ExecutionDomain.DIRECT, requires=("a", "b"))
    d = tool.to_def()
    assert d.name == "calc"
    assert d.domain == ExecutionDomain.DIRECT
    assert d.requires == ("a", "b")
    assert d.input_schema == {"type": "object", "properties": {"x": {"type": "string"}}}


# ── ToolRegistry 注册 ──


def test_register_and_get() -> None:
    """注册后可按名获取, has 返回 True."""
    reg = ToolRegistry()
    tool = _FakeTool("calc", ExecutionDomain.DIRECT)
    reg.register(tool)
    assert reg.has("calc")
    assert reg.get("calc") is tool
    assert len(reg) == 1


def test_register_duplicate_raises() -> None:
    """重复注册同名工具抛 ValidationError."""
    reg = ToolRegistry()
    reg.register(_FakeTool("calc"))
    with pytest.raises(ValidationError, match="已注册"):
        reg.register(_FakeTool("calc"))


def test_register_empty_name_raises() -> None:
    """空 name 注册抛 ValidationError."""
    reg = ToolRegistry()
    with pytest.raises(ValidationError, match="不能为空"):
        reg.register(_FakeTool(""))


def test_get_not_found_raises() -> None:
    """获取未注册工具抛 NotFoundError."""
    reg = ToolRegistry()
    with pytest.raises(NotFoundError):
        reg.get("missing")


# ── 查询接口 ──


def test_list_all_preserves_register_order() -> None:
    """list_all 按注册顺序返回."""
    reg = ToolRegistry()
    reg.register(_FakeTool("a"))
    reg.register(_FakeTool("b"))
    reg.register(_FakeTool("c"))
    assert [t.name for t in reg.list_all()] == ["a", "b", "c"]


def test_list_defs() -> None:
    """list_defs 返回全部工具的 ToolDef."""
    reg = ToolRegistry()
    reg.register(_FakeTool("a", ExecutionDomain.DIRECT))
    defs = reg.list_defs()
    assert len(defs) == 1
    assert defs[0].name == "a"
    assert defs[0].domain == ExecutionDomain.DIRECT


def test_list_by_domain() -> None:
    """list_by_domain 仅返回指定域的工具."""
    reg = ToolRegistry()
    reg.register(_FakeTool("calc", ExecutionDomain.DIRECT))
    reg.register(_FakeTool("file", ExecutionDomain.SKILL_ONLY))
    reg.register(_FakeTool("search", ExecutionDomain.SUBAGENT_ONLY))
    assert [t.name for t in reg.list_by_domain(ExecutionDomain.DIRECT)] == ["calc"]
    assert [t.name for t in reg.list_by_domain(ExecutionDomain.SKILL_ONLY)] == ["file"]


def test_list_names() -> None:
    """list_names 返回全部工具名."""
    reg = ToolRegistry()
    reg.register(_FakeTool("a"))
    reg.register(_FakeTool("b"))
    assert reg.list_names() == ["a", "b"]


def test_defs_by_names_skips_missing() -> None:
    """defs_by_names 跳过未注册项, 不抛错."""
    reg = ToolRegistry()
    reg.register(_FakeTool("a"))
    reg.register(_FakeTool("b"))
    defs = reg.defs_by_names(["a", "missing", "b"])
    assert [d.name for d in defs] == ["a", "b"]
