"""短期记忆单测 - Redis 会话级消息缓存."""

from knowflow.memory.short_term import ShortTermMemory
from tests.fakes import FakeRedisList


def _memory() -> tuple[ShortTermMemory, FakeRedisList]:
    redis = FakeRedisList()
    return ShortTermMemory(redis, ttl_seconds=3600), redis


async def test_add_and_get_recent() -> None:
    """写入多条消息, 取最近 n 条(新→旧)."""
    mem, _ = _memory()
    for i in range(5):
        await mem.add("s1", "user", f"消息{i}")
    recent = await mem.get_recent("s1", n=3)
    assert [m["content"] for m in recent] == ["消息2", "消息3", "消息4"]
    assert recent[-1]["role"] == "user"


async def test_add_refreshes_ttl() -> None:
    """每次写入刷新 TTL(expire 被调用)."""
    mem, redis = _memory()
    await mem.add("s1", "user", "x")
    await mem.add("s1", "assistant", "y")
    assert redis.expired == [("mem:short:s1", 3600), ("mem:short:s1", 3600)]


async def test_clear_and_count() -> None:
    mem, _ = _memory()
    await mem.add("s1", "user", "a")
    await mem.add("s1", "user", "b")
    assert await mem.count("s1") == 2
    await mem.clear("s1")
    assert await mem.count("s1") == 0
    assert await mem.get_recent("s1") == []


async def test_session_isolation() -> None:
    """不同会话 key 隔离."""
    mem, _ = _memory()
    await mem.add("s1", "user", "a")
    await mem.add("s2", "user", "b")
    assert await mem.get_recent("s1") == [{"role": "user", "content": "a"}]
    assert await mem.get_recent("s2") == [{"role": "user", "content": "b"}]
