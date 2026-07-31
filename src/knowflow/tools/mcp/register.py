"""MCP Server 注册工厂 - 连接远程 Server, 将工具适配注册进 ToolRegistry.

完整链路: 注册(连接 + list_tools) → 治理(适配为 BaseTool 纳入执行域) →
隔离(VisibilityCalculator 按域/Skill 可见) → 调用(gateway 转发) →
trace(工具调用经 ToolOrchestrator 统一记录). 单个 Server 连接失败
不阻塞其他注册(降级为告警).
"""

from knowflow.core.constants import ExecutionDomain
from knowflow.core.logging import get_logger
from knowflow.tools.mcp.adapter import McpToolAdapter
from knowflow.tools.mcp.gateway import McpGateway
from knowflow.tools.registry import ToolRegistry

logger = get_logger(__name__)


async def register_mcp_server(
    registry: ToolRegistry,
    server_id: str,
    command: str,
    args: list[str] | None = None,
    *,
    domain: ExecutionDomain = ExecutionDomain.SKILL_ONLY,
    env: dict[str, str] | None = None,
    allow_tools: list[str] | None = None,
) -> list[str]:
    """连接 MCP Server 并注册工具进 registry(可白名单过滤).

    Args:
        registry: 目标工具注册表.
        server_id: 逻辑名(工具名前缀 mcp_{server_id}_*).
        command: server 启动命令(可执行文件路径).
        args: 启动参数.
        domain: 工具执行域(默认 SKILL_ONLY: 需 Skill 激活才可见).
        env: 附加环境变量.
        allow_tools: 工具白名单; 非 None 时只注册白名单内工具
            (官方全量 server 接入时控制可见工具膨胀, 未命中静默跳过).

    Returns:
        成功注册的工具名列表. Server 连接失败返回空列表并告警(不抛出).
    """
    gateway = McpGateway(command, args, env)
    try:
        infos = await gateway.list_tools()
    except Exception as exc:
        logger.warning("mcp.server_unavailable", server_id=server_id, error=str(exc))
        return []

    registered: list[str] = []
    for info in infos:
        if allow_tools is not None and info.name not in allow_tools:
            logger.info("mcp.tool_filtered", server_id=server_id, tool=info.name)
            continue
        adapter = McpToolAdapter(server_id, info, gateway, domain=domain)
        try:
            registry.register(adapter)
            registered.append(adapter.name)
        except Exception as exc:
            # 单工具注册失败(如名称冲突)跳过, 不阻塞同 server 其他工具
            logger.warning(
                "mcp.tool_register_failed", server_id=server_id, tool=info.name, error=str(exc)
            )
    logger.info("mcp.server_registered", server_id=server_id, tools=registered)
    return registered
