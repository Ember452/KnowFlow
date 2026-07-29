"""记忆检索工具单测 - 召回成功/召回失败降级."""

from dataclasses import dataclass

import pytest

from knowflow.tools.builtin.memory_tool import MemoryTool


@dataclass(frozen=True)
class _FakeHit:
    content: str
    importance: float = 6.0
    score: float = 0.9


class _FakeRecaller:
    def __init__(self, hits: list[_FakeHit] | None = None, raise_error: bool = False) -> None:
        self._hits = hits or []
        self._raise_error = raise_error
        self.calls: list[tuple[str, str, int | None]] = []

    async def recall(self, query: str, user_id: str, top_k: int | None = None) -> list[_FakeHit]:
        self.calls.append((query, user_id, top_k))
        if self._raise_error:
            raise RuntimeError("memory down")
        return list(self._hits)


@pytest.mark.asyncio
async def test_execute_returns_recalled_hits() -> None:
    """召回成功: 输出内容/重要性/分数列表."""
    recaller = _FakeRecaller([_FakeHit("用户偏好简洁回答")])
    result = await MemoryTool(recaller=recaller).execute(query="用户偏好", user_id="u1", top_k=3)
    assert result.success is True
    assert result.output == [{"content": "用户偏好简洁回答", "importance": 6.0, "score": 0.9}]
    assert recaller.calls == [("用户偏好", "u1", 3)]


@pytest.mark.asyncio
async def test_execute_defaults_user_id() -> None:
    """未传 user_id 时使用默认用户标识."""
    recaller = _FakeRecaller([_FakeHit("记忆")])
    await MemoryTool(recaller=recaller, default_user_id="anonymous").execute(query="q")
    assert recaller.calls == [("q", "anonymous", None)]


@pytest.mark.asyncio
async def test_execute_failure_returns_failed_result() -> None:
    """召回异常: 返回失败 ToolResult(不抛出)."""
    recaller = _FakeRecaller(raise_error=True)
    result = await MemoryTool(recaller=recaller).execute(query="q")
    assert result.success is False
    assert "memory down" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_empty_hits() -> None:
    """无命中: success=True + 空列表."""
    result = await MemoryTool(recaller=_FakeRecaller()).execute(query="q")
    assert result.success is True
    assert result.output == []
