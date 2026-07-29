"""内置工具包 - 提供 build_default_registry 构造全部内置工具的注册表.

依赖注入: retriever(检索器单例) 与 workspace_manager(沙盒管理器) 由调用方提供,
使工具可测试(fake 注入). 未提供时检索/文件工具使用懒加载单例.
"""

from typing import Any

from knowflow.tools.builtin.calculator import CalculatorTool
from knowflow.tools.builtin.file_tools import FileListTool, FileReadTool, FileWriteTool
from knowflow.tools.builtin.memory_tool import MemoryTool
from knowflow.tools.builtin.retrieval_tool import RetrievalTool
from knowflow.tools.builtin.search_tool import SearchTool
from knowflow.tools.registry import ToolRegistry


def build_default_registry(
    retriever: Any | None = None,
    workspace_manager: Any | None = None,
    recaller: Any | None = None,
) -> ToolRegistry:
    """构造含全部内置工具的注册表.

    Args:
        retriever: 检索器(实现 async retrieve). None 时懒加载 deps.get_retriever.
        workspace_manager: 沙盒管理器. None 时用 db.minio 单例构造 WorkspaceManager.
        recaller: 记忆召回器(实现 async recall). None 时 MemoryTool 懒加载.

    Returns:
        已注册 7 个内置工具的 ToolRegistry.
    """
    if retriever is None:
        from knowflow.api.deps import get_retriever

        retriever = get_retriever()
    if workspace_manager is None:
        from knowflow.db.minio import get_minio
        from knowflow.sandbox.workspace import WorkspaceManager

        workspace_manager = WorkspaceManager(get_minio())

    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(RetrievalTool(retriever))
    registry.register(MemoryTool(recaller))
    registry.register(FileReadTool(workspace_manager))
    registry.register(FileWriteTool(workspace_manager))
    registry.register(FileListTool(workspace_manager))
    registry.register(SearchTool())
    return registry
