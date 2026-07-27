"""检索结果缓存 - 基于 Redis, md5(query) 作 key, JSON 序列化.

Redis 不可用时降级为 no-op + warning, 不阻塞检索.
"""

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger
from knowflow.retrieval.hybrid_search import ChunkScore

logger = get_logger(__name__)

# 缓存 key 前缀, 避免与其他模块冲突
_KEY_PREFIX = "knowflow:retrieval:"


class RetrievalCache:
    """检索结果缓存. 封装 Redis get/set, 失败时降级."""

    def __init__(
        self,
        redis: Any | None = None,
        *,
        ttl: int | None = None,
    ) -> None:
        """初始化.

        Args:
            redis: Redis 客户端(单测可注入 fake). None 时调 get_redis().
            ttl: 缓存 TTL(秒), None 时取 settings.retrieval_cache_ttl_seconds.
        """
        self._redis: Any | None = redis
        self._ttl = ttl if ttl is not None else get_settings().retrieval_cache_ttl_seconds

    def _get_redis(self) -> Any | None:
        """懒加载 Redis 单例."""
        if self._redis is not None:
            return self._redis
        try:
            from knowflow.db.redis import get_redis

            self._redis = get_redis()
            return self._redis
        except RuntimeError:
            # Redis 未初始化, 降级
            logger.warning("cache.redis_not_initialized")
            return None

    @staticmethod
    def _make_key(
        query: str,
        *,
        top_k: int,
        with_rerank: bool,
    ) -> str:
        """md5(query+检索参数) 作 key, 避免特殊字符与超长 query.

        检索参数(返回条数/精排开关)必须进 key: 同一 query 不同参数
        会产生不同结果, 否则参数不一致的请求会命中彼此的缓存返回错误结果.
        """
        digest = hashlib.md5(f"{query}|{top_k}|{with_rerank}".encode()).hexdigest()
        return f"{_KEY_PREFIX}{digest}"

    async def get(
        self,
        query: str,
        *,
        top_k: int,
        with_rerank: bool,
    ) -> list[ChunkScore] | None:
        """读缓存.

        Args:
            query: 查询文本.
            top_k: 返回条数(参与缓存键).
            with_rerank: 是否启用精排(参与缓存键).

        Returns:
            命中时返回 ChunkScore 列表; 未命中或 Redis 不可用时返回 None.
        """
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            key = self._make_key(query, top_k=top_k, with_rerank=with_rerank)
            raw = await redis.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            return [ChunkScore(**item) for item in data]
        except Exception as exc:
            logger.warning("cache.get_failed", error=str(exc))
            return None

    async def set(
        self,
        query: str,
        results: Sequence[ChunkScore],
        *,
        top_k: int,
        with_rerank: bool,
    ) -> None:
        """写缓存.

        Args:
            query: 查询文本.
            results: 检索结果列表.
            top_k: 返回条数(参与缓存键).
            with_rerank: 是否启用精排(参与缓存键).
        """
        redis = self._get_redis()
        if redis is None:
            return
        try:
            key = self._make_key(query, top_k=top_k, with_rerank=with_rerank)
            data = json.dumps(
                [{"chunk_id": r.chunk_id, "score": r.score, "source": r.source} for r in results]
            )
            await redis.set(key, data, ex=self._ttl)
        except Exception as exc:
            logger.warning("cache.set_failed", error=str(exc))

    async def invalidate(
        self,
        query: str,
        *,
        top_k: int,
        with_rerank: bool,
    ) -> None:
        """失效单条缓存(参数须与写入时一致)."""
        redis = self._get_redis()
        if redis is None:
            return
        try:
            key = self._make_key(query, top_k=top_k, with_rerank=with_rerank)
            await redis.delete(key)
        except Exception as exc:
            logger.warning("cache.invalidate_failed", error=str(exc))

    async def clear_prefix(self, prefix: str = _KEY_PREFIX) -> None:
        """清空指定前缀的缓存. 默认清空全部检索缓存."""
        redis = self._get_redis()
        if redis is None:
            return
        try:
            # SCAN 避免阻塞 KEYS 命令
            async for key in redis.scan_iter(match=f"{prefix}*"):
                await redis.delete(key)
        except Exception as exc:
            logger.warning("cache.clear_prefix_failed", error=str(exc))
