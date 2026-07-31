"""MCP 工具接入单测 - 真实 stdio 协议往返(内置 demo server 子进程).

覆盖完整链路: 注册(连接+list_tools) → 治理(适配为 BaseTool) →
隔离(执行域/Skill 可见性) → 调用(gateway 转发) → 失败降级.
"""

import sys
from pathlib import Path

import pytest

from knowflow.core.constants import ExecutionDomain
from knowflow.tools.mcp.adapter import McpToolAdapter
from knowflow.tools.mcp.gateway import McpConnectionError, McpGateway, McpToolInfo
from knowflow.tools.mcp.register import register_mcp_server
from knowflow.tools.registry import ToolRegistry
from knowflow.tools.skill_schema import SkillDefinition
from knowflow.tools.visibility import VisibilityCalculator

# demo server 以子进程方式真实启动; PYTHONPATH 指向 src 保证 knowflow 可导入
_SERVER_ARGS = ["-m", "knowflow.tools.mcp.servers.demo"]
_SERVER_ENV = {"PYTHONPATH": str(Path(__file__).resolve().parents[3] / "src")}


def _gateway() -> McpGateway:
    return McpGateway(sys.executable, _SERVER_ARGS, _SERVER_ENV)


# ── 网关: 真实协议往返 ──


@pytest.mark.asyncio
async def test_list_tools_connects_to_demo_server() -> None:
    """list_tools 真实连接 demo server, 返回工具清单."""
    tools = await _gateway().list_tools()
    names = {t.name for t in tools}
    assert {"echo", "server_time"} <= names
    echo = next(t for t in tools if t.name == "echo")
    assert echo.description  # 工具描述已透传
    assert echo.input_schema  # 输入 schema 已透传


@pytest.mark.asyncio
async def test_call_tool_echo_roundtrip() -> None:
    """call_tool 真实往返: 参数透传 + 结果回传."""
    output = await _gateway().call_tool("echo", {"message": "hello"})
    assert output == "echo:hello"


@pytest.mark.asyncio
async def test_call_tool_error_propagates() -> None:
    """远程工具执行失败(is_error)时抛 McpConnectionError(上层降级)."""
    with pytest.raises(McpConnectionError):
        await _gateway().call_tool("boom", {})


@pytest.mark.asyncio
async def test_call_tool_bad_arguments_ignored_extra() -> None:
    """多余参数被远程 server 忽略, 正常返回(协议层宽容)."""
    adapter = McpToolAdapter("demo", McpToolInfo(name="echo"), _gateway())
    result = await adapter.execute(message="x", unexpected=1)
    assert result.success is True
    assert result.output == "echo:x"


# ── 注册: 适配进工具注册表 ──


@pytest.mark.asyncio
async def test_register_mcp_server_registers_adapted_tools() -> None:
    """注册工厂把远程工具适配为本地 BaseTool 进 registry(带 server 前缀)."""
    registry = ToolRegistry()
    registered = await register_mcp_server(registry, "demo", sys.executable, _SERVER_ARGS)
    assert set(registered) == {
        "mcp_demo_echo",
        "mcp_demo_server_time",
        "mcp_demo_boom",
        "mcp_demo_slow",
    }
    tool = registry.get("mcp_demo_echo")
    assert isinstance(tool, McpToolAdapter)
    assert tool.domain == ExecutionDomain.SKILL_ONLY
    assert tool.to_def().input_schema  # ToolDef 可序列化(注入/指标链路兼容)


@pytest.mark.asyncio
async def test_register_server_unavailable_returns_empty() -> None:
    """server 不可达(命令不存在)降级返回空列表, 不抛出."""
    registry = ToolRegistry()
    registered = await register_mcp_server(
        registry, "ghost", sys.executable, ["-m", "no.such.module"]
    )
    assert registered == []
    assert len(registry) == 0


@pytest.mark.asyncio
async def test_register_duplicate_server_skips_conflict() -> None:
    """同名工具重复注册: 单工具跳过, 不影响同 server 其他工具."""
    registry = ToolRegistry()
    await register_mcp_server(registry, "demo", sys.executable, _SERVER_ARGS)
    again = await register_mcp_server(registry, "demo", sys.executable, _SERVER_ARGS)
    assert again == []  # 全部名称冲突被跳过
    assert len(registry) == 4  # 首次注册的工具保留


@pytest.mark.asyncio
async def test_register_allow_tools_filters_whitelist() -> None:
    """allow_tools 白名单: 只注册白名单内工具, 未命中静默跳过."""
    from knowflow.core.exceptions import NotFoundError

    registry = ToolRegistry()
    registered = await register_mcp_server(
        registry, "demo", sys.executable, _SERVER_ARGS, allow_tools=["echo"]
    )
    assert registered == ["mcp_demo_echo"]
    with pytest.raises(NotFoundError):
        registry.get("mcp_demo_server_time")
    with pytest.raises(NotFoundError):
        registry.get("mcp_demo_boom")


@pytest.mark.asyncio
async def test_call_tool_timeout_raises_connection_error() -> None:
    """调用超时(远端挂死): 抛 McpConnectionError, 由上层降级."""
    gateway = McpGateway(sys.executable, _SERVER_ARGS, _SERVER_ENV, timeout=0.5)
    with pytest.raises(McpConnectionError, match="超时"):
        await gateway.call_tool("slow", {})


# ── 隔离: 执行域 + Skill 激活可见 ──


@pytest.mark.asyncio
async def test_mcp_tools_hidden_without_active_skill() -> None:
    """SKILL_ONLY 域 MCP 工具: 无 Skill 激活时对模型不可见(执行域隔离)."""
    registry = ToolRegistry()
    await register_mcp_server(registry, "demo", sys.executable, _SERVER_ARGS)
    visible = VisibilityCalculator().compute([], "main", registry)
    names = {t.name for t in visible}
    assert "mcp_demo_echo" not in names


@pytest.mark.asyncio
async def test_mcp_tools_visible_when_skill_active() -> None:
    """Skill 声明引用 MCP 工具并激活后, 工具进入模型可见集."""
    registry = ToolRegistry()
    await register_mcp_server(registry, "demo", sys.executable, _SERVER_ARGS)
    skill = SkillDefinition(name="demo", tools=["mcp_demo_echo"], enabled=True)
    visible = VisibilityCalculator().compute([skill], "main", registry)
    names = {t.name for t in visible}
    assert "mcp_demo_echo" in names
    assert "mcp_demo_server_time" not in names  # 未被 Skill 引用, 仍不可见


# ── 调用: 适配器经网关转发 ──


@pytest.mark.asyncio
async def test_mcp_adapter_execute_through_gateway() -> None:
    """适配器 execute 经网关真实调用远程工具并返回 ToolResult."""
    registry = ToolRegistry()
    await register_mcp_server(registry, "demo", sys.executable, _SERVER_ARGS)
    tool = registry.get("mcp_demo_echo")
    result = await tool.execute(message="KnowFlow")
    assert result.success is True
    assert result.output == "echo:KnowFlow"
    assert result.latency_ms >= 0
