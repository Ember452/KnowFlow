"""工具注入器单测 - LLM tools 参数构建与 Schema Token 估算.

inject() 输出 OpenAI function-calling 格式; schema_chars/schema_tokens 估算注入开销.
"""

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.base import ToolDef
from knowflow.tools.injector import Injector


def _def(name: str, schema: dict | None = None) -> ToolDef:
    return ToolDef(
        name=name,
        description=f"工具 {name}",
        domain=ExecutionDomain.DIRECT,
        input_schema=schema or {"type": "object", "properties": {"x": {"type": "string"}}},
    )


# ── inject ──


def test_inject_single_tool() -> None:
    """单工具注入为 OpenAI function 格式."""
    tools = Injector().inject([_def("calc")])
    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    fn = tools[0]["function"]
    assert fn["name"] == "calc"
    assert fn["description"] == "工具 calc"
    assert "properties" in fn["parameters"]


def test_inject_multiple_tools() -> None:
    """多工具按顺序注入."""
    tools = Injector().inject([_def("a"), _def("b")])
    assert [t["function"]["name"] for t in tools] == ["a", "b"]


def test_inject_empty() -> None:
    """空列表注入返回空."""
    assert Injector().inject([]) == []


# ── schema 估算 ──


def test_schema_chars_grows_with_tools() -> None:
    """schema_chars 随工具数增加."""
    inj = Injector()
    one = inj.schema_chars([_def("a")])
    two = inj.schema_chars([_def("a"), _def("b")])
    assert two > one


def test_schema_tokens_approximately_chars_div_4() -> None:
    """schema_tokens ≈ schema_chars / 4."""
    inj = Injector()
    tools = [_def("calc", {"type": "object", "properties": {"x": {"type": "string"}}})]
    chars = inj.schema_chars(tools)
    assert inj.schema_tokens(tools) == chars // 4


def test_schema_tokens_custom_chars_per_token() -> None:
    """可自定义 chars_per_token."""
    inj = Injector()
    tools = [_def("a")]
    chars = inj.schema_chars(tools)
    assert inj.schema_tokens(tools, chars_per_token=2) == chars // 2


def test_schema_tokens_empty() -> None:
    """空工具集 token 为 0."""
    assert Injector().schema_tokens([]) == 0
