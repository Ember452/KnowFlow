"""沙盒生命周期 - 会话级 TTL 清理与结束回收.

提供批量清理接口, 供 lifecycle/会话结束钩子调用. TTL 清理由上层按 session_ttl_seconds
调度(本模块只提供清理能力, 不内置定时器, 避免引入后台任务复杂度).
"""

from typing import Any

from knowflow.sandbox.workspace import WorkspaceManager


class SandboxLifecycle:
    """沙盒生命周期管理. 包装 WorkspaceManager 提供批量清理."""

    def __init__(self, workspace_manager: WorkspaceManager) -> None:
        self._ws = workspace_manager

    async def cleanup_session(self, session_id: int | str) -> int:
        """会话结束时清理其 workspace. 返回删除对象数."""
        return await self._ws.cleanup(session_id)

    async def cleanup_sessions(self, session_ids: list[Any]) -> dict[str, int]:
        """批量清理多个会话 workspace. 单会话失败不阻塞其余."""
        result: dict[str, int] = {}
        for sid in session_ids:
            key = str(sid)
            try:
                result[key] = await self._ws.cleanup(sid)
            except Exception:
                result[key] = -1
        return result
