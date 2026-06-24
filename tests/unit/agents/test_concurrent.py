"""并发执行器单测 - asyncio.gather 并发/超时/降级."""

import asyncio

import pytest

from knowflow.agents.concurrent import SubtaskResult, run_concurrent


async def _fast(subtask_id: str, delay: float, output: str = "ok") -> SubtaskResult:
    """固定延迟后返回成功结果."""
    await asyncio.sleep(delay)
    return SubtaskResult(subtask_id=subtask_id, success=True, output=output)


@pytest.mark.asyncio
async def test_run_concurrent_executes_all() -> None:
    """全部子任务并发执行, 结果顺序与输入一致."""
    results = await run_concurrent(
        {
            "t1": _fast("t1", 0.01, "A"),
            "t2": _fast("t2", 0.01, "B"),
            "t3": _fast("t3", 0.01, "C"),
        },
        timeout=5.0,
    )
    assert [r.subtask_id for r in results] == ["t1", "t2", "t3"]
    assert all(r.success for r in results)
    assert [r.output for r in results] == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_run_concurrent_speedup() -> None:
    """3 个各 0.2s 的子任务并发执行, 总耗时接近最慢单个而非串行和."""
    start = asyncio.get_event_loop().time()
    results = await run_concurrent(
        {"t1": _fast("t1", 0.2), "t2": _fast("t2", 0.2), "t3": _fast("t3", 0.2)},
        timeout=5.0,
    )
    elapsed = asyncio.get_event_loop().time() - start
    assert all(r.success for r in results)
    # 并发总耗时 < 串行总耗时(0.6s) 的一半
    assert elapsed < 0.4


@pytest.mark.asyncio
async def test_run_concurrent_timeout_degrades() -> None:
    """超时子任务降级为 failed, 不阻塞其他子任务."""

    async def slow(subtask_id: str) -> SubtaskResult:
        await asyncio.sleep(0.5)
        return SubtaskResult(subtask_id=subtask_id, success=True, output="late")

    start = asyncio.get_event_loop().time()
    results = await run_concurrent(
        {"t1": slow("t1"), "t2": _fast("t2", 0.01, "fast")},
        timeout=0.1,
    )
    elapsed = asyncio.get_event_loop().time() - start
    by_id = {r.subtask_id: r for r in results}
    assert by_id["t1"].success is False
    assert "超时" in (by_id["t1"].error or "")
    assert by_id["t2"].success is True
    assert elapsed < 0.3  # 未被慢任务阻塞到完成


@pytest.mark.asyncio
async def test_run_concurrent_exception_degrades() -> None:
    """子任务抛异常时降级为 failed 并记录错误."""

    async def boom(subtask_id: str) -> SubtaskResult:
        raise RuntimeError("子任务内部错误")

    results = await run_concurrent({"t1": boom("t1")}, timeout=5.0)
    assert len(results) == 1
    assert results[0].success is False
    assert "子任务内部错误" in (results[0].error or "")


@pytest.mark.asyncio
async def test_run_concurrent_empty() -> None:
    """空输入返回空列表."""
    assert await run_concurrent({}, timeout=5.0) == []


@pytest.mark.asyncio
async def test_run_concurrent_on_timeout_callback() -> None:
    """on_timeout 回调可定制超时降级结果."""

    async def slow(subtask_id: str) -> SubtaskResult:
        await asyncio.sleep(0.5)
        return SubtaskResult(subtask_id=subtask_id, success=True, output="late")

    def fallback(subtask_id: str) -> SubtaskResult:
        return SubtaskResult(subtask_id=subtask_id, success=False, output="降级", error="timeout")

    results = await run_concurrent({"t1": slow("t1")}, timeout=0.05, on_timeout=fallback)
    assert results[0].success is False
    assert results[0].output == "降级"
