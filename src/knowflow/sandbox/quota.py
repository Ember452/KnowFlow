"""配额管理 - 单会话 workspace 容量限制(默认 100MB).

写入前校验: 已用 + 新增 ≤ workspace_quota_bytes. 用量按 MinIO 对象 size 求和统计.
超限抛 ValidationError, 由 FileOps 上报, 工具层不感知.
"""

from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import ValidationError
from knowflow.sandbox.minio_backend import MinioBackend
from knowflow.sandbox.virtual_path import VirtualPathMapper


class QuotaManager:
    """单会话 workspace 配额管理器."""

    def __init__(
        self,
        backend: MinioBackend,
        session_id: int | str,
        settings: Settings | None = None,
    ) -> None:
        self._backend = backend
        self._session_id = str(session_id)
        self._prefix = f"{VirtualPathMapper(session_id).session_prefix}/"
        self._settings = settings or get_settings()
        self._quota = self._settings.workspace_quota_bytes

    @property
    def quota(self) -> int:
        return self._quota

    async def usage(self) -> int:
        """当前会话 workspace 已用字节数."""
        objs = await self._backend.list(self._prefix)
        return sum(size for _, size in objs)

    async def check(self, additional_bytes: int) -> None:
        """校验写入 additional_bytes 后是否超配额; 超限抛 ValidationError."""
        if additional_bytes < 0:
            raise ValidationError(f"非法写入大小: {additional_bytes}")
        used = await self.usage()
        if used + additional_bytes > self._quota:
            raise ValidationError(
                f"workspace 配额超限: 已用 {used} + 新增 {additional_bytes} > 上限 {self._quota}",
                details={"used": used, "additional": additional_bytes, "quota": self._quota},
            )
