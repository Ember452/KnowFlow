"""MinIO 存储后端 - 对象 CRUD 封装(沙盒文件系统后端).

MinIO 客户端为同步, 所有操作经 asyncio.to_thread 避免阻塞事件循环.
依赖 db/minio.py 的 Minio 单例, 测试可注入 FakeMinio(实现 put/get/list/remove/stat).
"""

import asyncio
import io
from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.core.exceptions import NotFoundError
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


class MinioBackend:
    """MinIO 对象存储后端. 封装 bucket 内对象的 CRUD."""

    def __init__(self, minio_client: Any, settings: Settings | None = None) -> None:
        self._minio = minio_client
        self._settings = settings or get_settings()
        self._bucket = self._settings.minio_bucket

    async def write(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """写入对象(覆盖式)."""
        await asyncio.to_thread(
            self._minio.put_object,
            self._bucket,
            key,
            io.BytesIO(data),
            len(data),
            content_type,
        )

    async def read(self, key: str) -> bytes:
        """读取对象全部内容; 不存在时抛 NotFoundError."""
        try:
            response = await asyncio.to_thread(self._minio.get_object, self._bucket, key)
        except Exception as exc:
            raise NotFoundError(f"沙盒对象不存在: {key}") from exc
        try:
            data: bytes = response.read()
            return data
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
            release = getattr(response, "release_conn", None)
            if callable(release):
                release()

    # NOTE: _list_sync 须定义在 list 方法之前, 否则类体内 `list` 名称被同名方法遮蔽,
    # 导致本函数返回标注 list[Any] 在定义时把 list 当作函数对象而报错.
    def _list_sync(self, prefix: str) -> list[Any]:
        return list(self._minio.list_objects(self._bucket, prefix=prefix, recursive=True))

    async def list(self, prefix: str) -> list[tuple[str, int]]:
        """递归列出 prefix 下对象, 返回 [(object_name, size_bytes)]."""
        objects = await asyncio.to_thread(self._list_sync, prefix)
        return [(o.object_name, int(getattr(o, "size", 0) or 0)) for o in objects]

    async def delete(self, key: str) -> None:
        """删除对象(幂等, 不存在不报错)."""
        await asyncio.to_thread(self._minio.remove_object, self._bucket, key)

    async def exists(self, key: str) -> bool:
        """对象是否存在."""
        try:
            await asyncio.to_thread(self._minio.stat_object, self._bucket, key)
            return True
        except Exception:
            return False

    async def stat(self, key: str) -> tuple[bool, int]:
        """返回 (exists, size); 不存在时 size=0."""
        try:
            obj = await asyncio.to_thread(self._minio.stat_object, self._bucket, key)
            return True, int(getattr(obj, "size", 0) or 0)
        except Exception:
            return False, 0
