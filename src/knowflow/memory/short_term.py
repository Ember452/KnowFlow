"""短期记忆 - Redis 会话级消息缓存, TTL 过期自动清理.

key 格式: mem:short:{session_id} -> list[{"role", "content"}].
提供 add/get_recent/clear/count, 供沉淀(sediment)取最近消息.
"""

import json
from typing import Any

from knowflow.core.config import Settings, get_settings

_PREFIX = "mem:short:"


class ShortTermMemory:
    """Redis 会话短期记忆. redis 需支持 async rpush/lrange/expire/delete/llen."""

    def __init__(
        self,
        redis: Any,
        ttl_seconds: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._redis = redis
        self._settings = settings or get_settings()
        self._ttl = ttl_seconds if ttl_seconds is not None else self._settings.session_ttl_seconds

    @staticmethod
    def _key(session_id: int | str) -> str:
        return f"{_PREFIX}{session_id}"

    async def add(self, session_id: int | str, role: str, content: str) -> None:
        """追加一条消息并刷新 TTL."""
        key = self._key(session_id)
        payload = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        await self._redis.rpush(key, payload)
        await self._redis.expire(key, self._ttl)

    async def get_recent(self, session_id: int | str, n: int = 20) -> list[dict[str, str]]:
        """取最近 n 条消息(新→旧排序, 便于倒序处理)."""
        items = await self._redis.lrange(self._key(session_id), -n, -1)
        messages: list[dict[str, str]] = []
        for raw in items:
            try:
                messages.append(json.loads(raw))
            except (TypeError, ValueError):
                continue
        return messages

    async def clear(self, session_id: int | str) -> None:
        """清空会话短期记忆."""
        await self._redis.delete(self._key(session_id))

    async def count(self, session_id: int | str) -> int:
        """当前会话短期消息条数."""
        return int(await self._redis.llen(self._key(session_id)))
