"""文件操作 - read/write/list/delete/exists, 编排权限校验/映射/配额/后端.

session 级实例: 构造时绑定 session_id, 所有方法对工具暴露虚拟路径.
流程统一为: AccessControl 校验 → VirtualPathMapper 映射 → (写入时) Quota 校验 →
MinioBackend 执行. 跨会话访问在映射层即被拒绝.
"""

from dataclasses import dataclass

from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import NotFoundError
from knowflow.sandbox.access_control import AccessControl
from knowflow.sandbox.minio_backend import MinioBackend
from knowflow.sandbox.quota import QuotaManager
from knowflow.sandbox.virtual_path import VirtualPathMapper

WORKSPACE_ROOT = "/workspace/"


@dataclass(frozen=True)
class FileInfo:
    """沙盒文件信息(虚拟路径 + 字节大小)."""

    virtual_path: str
    size: int


class FileOps:
    """会话级沙盒文件操作. 每个会话构造一个实例, 绑定 session_id."""

    def __init__(
        self,
        session_id: int | str,
        backend: MinioBackend,
        mapper: VirtualPathMapper,
        access_control: AccessControl,
        quota: QuotaManager,
        settings: Settings | None = None,
    ) -> None:
        self._session_id = str(session_id)
        self._backend = backend
        self._mapper = mapper
        self._access = access_control
        self._quota = quota
        self._settings = settings or get_settings()

    @property
    def session_id(self) -> str:
        return self._session_id

    async def write(
        self,
        virtual_path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """写入文件(覆盖式). 返回规范化后的虚拟路径."""
        path = self._access.validate(virtual_path)
        key = self._mapper.to_real(path)
        await self._quota.check(len(content))
        await self._backend.write(key, content, content_type)
        return path

    async def read(self, virtual_path: str) -> bytes:
        """读取文件内容; 不存在抛 NotFoundError."""
        path = self._access.validate(virtual_path)
        key = self._mapper.to_real(path)
        exists, _ = await self._backend.stat(key)
        if not exists:
            raise NotFoundError(f"沙盒文件不存在: {path}")
        return await self._backend.read(key)

    async def list(self, virtual_dir: str = WORKSPACE_ROOT) -> list[FileInfo]:
        """列出目录下文件(递归). 默认列 workspace 根."""
        path = self._access.validate(virtual_dir)
        key_prefix = self._mapper.to_real(path)
        objs = await self._backend.list(key_prefix)
        return [
            FileInfo(virtual_path=self._mapper.to_virtual(name), size=size) for name, size in objs
        ]

    async def delete(self, virtual_path: str) -> bool:
        """删除文件; 返回是否删除(不存在返回 False)."""
        path = self._access.validate(virtual_path)
        key = self._mapper.to_real(path)
        exists, _ = await self._backend.stat(key)
        if not exists:
            return False
        await self._backend.delete(key)
        return True

    async def exists(self, virtual_path: str) -> bool:
        """文件是否存在."""
        path = self._access.validate(virtual_path)
        key = self._mapper.to_real(path)
        exists, _ = await self._backend.stat(key)
        return exists

    async def usage(self) -> int:
        """当前 workspace 已用字节数(供工具/上层展示)."""
        return await self._quota.usage()
