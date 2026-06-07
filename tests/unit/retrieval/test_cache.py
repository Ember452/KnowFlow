"""cache 单测 - mock Redis, 验证 hit/miss/set/invalidate / TTL / 降级 / 序列化往返."""

import pytest

from knowflow.retrieval.cache import RetrievalCache
from knowflow.retrieval.hybrid_search import ChunkScore


class FakeRedis:
    """fake Redis: 内存字典存储, 模拟 get/set/delete/scan_iter."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, int]] = []
        self.delete_calls: list[str] = []
        self.fail = False  # 模拟故障开关

    async def get(self, key: str) -> str | None:
        if self.fail:
            raise RuntimeError("redis down")
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.fail:
            raise RuntimeError("redis down")
        self.store[key] = value
        self.set_calls.append((key, value, ex if ex is not None else 0))

    async def delete(self, key: str) -> None:
        if self.fail:
            raise RuntimeError("redis down")
        self.store.pop(key, None)
        self.delete_calls.append(key)

    async def scan_iter(self, *, match: str):  # type: ignore[no-untyped-def]
        # 简化: 返回所有以 match 前缀(去掉 *) 开头的 key
        prefix = match.rstrip("*")
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                yield key


@pytest.mark.asyncio
async def test_cache_miss() -> None:
    """未命中返回 None."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    assert await cache.get("query") is None


@pytest.mark.asyncio
async def test_cache_hit_after_set() -> None:
    """set 后 get 命中, 返回反序列化的 ChunkScore 列表."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    results = [
        ChunkScore(chunk_id=1, score=0.9, source="hybrid"),
        ChunkScore(chunk_id=2, score=0.5, source="expand"),
    ]
    await cache.set("query", results)
    cached = await cache.get("query")
    assert cached is not None
    assert len(cached) == 2
    assert cached[0].chunk_id == 1
    assert cached[0].score == 0.9
    assert cached[0].source == "hybrid"


@pytest.mark.asyncio
async def test_cache_ttl_set() -> None:
    """set 时 TTL 被正确传递."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=120)
    await cache.set("query", [ChunkScore(chunk_id=1, score=0.5, source="hybrid")])
    assert len(redis.set_calls) == 1
    _, _, ex = redis.set_calls[0]
    assert ex == 120


@pytest.mark.asyncio
async def test_cache_invalidate() -> None:
    """invalidate 删除单条缓存."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    await cache.set("query", [ChunkScore(chunk_id=1, score=0.5, source="hybrid")])
    assert await cache.get("query") is not None
    await cache.invalidate("query")
    assert await cache.get("query") is None


@pytest.mark.asyncio
async def test_cache_clear_prefix() -> None:
    """clear_prefix 清空所有检索缓存."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    await cache.set("q1", [ChunkScore(chunk_id=1, score=0.5, source="hybrid")])
    await cache.set("q2", [ChunkScore(chunk_id=2, score=0.3, source="hybrid")])
    assert len(redis.store) == 2
    await cache.clear_prefix()
    assert len(redis.store) == 0


@pytest.mark.asyncio
async def test_cache_redis_failure_degrades_get() -> None:
    """Redis 故障时 get 降级返回 None, 不抛异常."""
    redis = FakeRedis()
    redis.fail = True
    cache = RetrievalCache(redis=redis, ttl=60)
    assert await cache.get("query") is None


@pytest.mark.asyncio
async def test_cache_redis_failure_degrades_set() -> None:
    """Redis 故障时 set 降级为 no-op, 不抛异常."""
    redis = FakeRedis()
    redis.fail = True
    cache = RetrievalCache(redis=redis, ttl=60)
    # 不抛异常
    await cache.set("query", [ChunkScore(chunk_id=1, score=0.5, source="hybrid")])
    assert len(redis.store) == 0


@pytest.mark.asyncio
async def test_cache_redis_not_initialized() -> None:
    """Redis 未初始化时降级, get 返回 None, set 为 no-op."""
    cache = RetrievalCache(redis=None, ttl=60)
    assert await cache.get("query") is None
    await cache.set("query", [ChunkScore(chunk_id=1, score=0.5, source="hybrid")])
    # 无异常即通过


@pytest.mark.asyncio
async def test_cache_serialization_roundtrip() -> None:
    """JSON 序列化往返: set 的数据能被 get 完整还原."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    original = [
        ChunkScore(chunk_id=i, score=0.1 * i, source="hybrid" if i % 2 == 0 else "expand")
        for i in range(1, 6)
    ]
    await cache.set("test", original)
    restored = await cache.get("test")
    assert restored is not None
    assert len(restored) == len(original)
    for orig, rest in zip(original, restored, strict=True):
        assert orig.chunk_id == rest.chunk_id
        assert orig.score == rest.score
        assert orig.source == rest.source


@pytest.mark.asyncio
async def test_cache_key_md5_hashed() -> None:
    """缓存 key 使用 md5 hash, 避免特殊字符."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    await cache.set("hello world", [])
    # key 应为 md5("hello world") 而非原文
    import hashlib

    expected_key = f"knowflow:retrieval:{hashlib.md5(b'hello world').hexdigest()}"
    assert expected_key in redis.store


@pytest.mark.asyncio
async def test_cache_empty_results() -> None:
    """空结果列表也能缓存与读取."""
    redis = FakeRedis()
    cache = RetrievalCache(redis=redis, ttl=60)
    await cache.set("query", [])
    cached = await cache.get("query")
    assert cached == []
