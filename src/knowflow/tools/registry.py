"""工具注册表 - 工具注册/查询/按执行域过滤.

启动时注册全部内置工具, 运行时按执行域/名称查询. 不感知 Skill 激活状态,
可见性计算由 visibility.py 负责.
"""

from knowflow.core.constants import ExecutionDomain
from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.core.logging import get_logger
from knowflow.tools.base import BaseTool, ToolDef

logger = get_logger(__name__)


class ToolRegistry:
    """工具注册表. 名称唯一, 重复注册抛错."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValidationError("工具 name 不能为空")
        if tool.name in self._tools:
            raise ValidationError(f"工具已注册: {tool.name}")
        self._tools[tool.name] = tool
        logger.info("tools.registered", tool=tool.name, domain=tool.domain.value)

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            raise NotFoundError(f"工具未注册: {name}")
        return tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def list_defs(self) -> list[ToolDef]:
        return [t.to_def() for t in self._tools.values()]

    def list_by_domain(self, domain: ExecutionDomain) -> list[BaseTool]:
        return [t for t in self._tools.values() if t.domain == domain]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def defs_by_names(self, names: list[str]) -> list[ToolDef]:
        """按名称批量取 ToolDef; 缺失项跳过(调用方按需校验)."""
        return [self._tools[n].to_def() for n in names if n in self._tools]

    def __len__(self) -> int:
        return len(self._tools)
