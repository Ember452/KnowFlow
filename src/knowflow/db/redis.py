"""Redis 异步连接池. 会话级短期记忆 / 限流 / 任务队列共用."""

from redis.asyncio import Redis

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_redis: Redis | None = None


async def init_redis() -> Redis:
    """建立 Redis 连接并 ping 验证."""
    global _redis
    settings = get_settings()
    _redis = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=20,
    )
    await _redis.ping()
    logger.info("db.redis_initialized", url=settings.redis_url)
    return _redis


async def dispose_redis() -> None:
    """关闭 Redis 连接池."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        logger.info("db.redis_disposed")
    _redis = None


def get_redis() -> Redis:
    """获取 Redis 客户端(已初始化时)."""
    if _redis is None:
        raise RuntimeError("Redis not initialized; call init_redis() first")
    return _redis
