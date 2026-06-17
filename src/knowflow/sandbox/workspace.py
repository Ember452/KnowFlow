"""工作区管理 - 会话级 workspace 创建/清理, 产出 session-scoped FileOps.

路径格式: sessions/{session_id}/workspace/. workspace 不需显式创建(MinIO 前缀扁平),
首次写入即生效; cleanup 按前缀列出并删除全部对象, 用于会话结束清理.
"""

from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.sandbox.access_control import AccessControl
from knowflow.sandbox.file_ops import FileOps
from knowflow.sandbox.minio_backend import MinioBackend
from knowflow.sandbox.quota import QuotaManager
from knowflow.sandbox.virtual_path import VirtualPathMapper

logger = get_logger(__name__)


class WorkspaceManager:
    """沙盒工作区管理器. 持有 MinioBackend, 为每个会话产出 FileOps."""

    def __init__(self, minio_client: Any, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._backend = MinioBackend(minio_client, self._settings)

    def for_session(self, session_id: int | str) -> FileOps:
        """构造会话级 FileOps(绑定 session_id 与配额)."""
        sid = str(session_id)
        mapper = VirtualPathMapper(sid)
        access = AccessControl(sid)
        quota = QuotaManager(self._backend, sid, self._settings)
        return FileOps(sid, self._backend, mapper, access, quota, self._settings)

    async def cleanup(self, session_id: int | str) -> int:
        """清理会话 workspace 全部对象; 返回删除数. 用于会话结束/过期清理."""
        sid = str(session_id)
        prefix = f"{VirtualPathMapper(sid).session_prefix}/"
        objs = await self._backend.list(prefix)
        for name, _ in objs:
            await self._backend.delete(name)
        logger.info("sandbox.workspace_cleaned", session_id=sid, removed=len(objs))
        return len(objs)

    async def usage(self, session_id: int | str) -> int:
        """查询会话 workspace 已用字节数."""
        return await self.for_session(session_id).usage()
