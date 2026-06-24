"""并发执行器 - asyncio.gather 并发执行子任务 + 超时 + 降级.

单个子任务失败/超时不阻塞整体(降级), 对应子任务结果标记 failed;
全部子任务并发执行, 总耗时为最慢子任务耗时.
"""

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubtaskResult:
    """单个子任务执行结果(供汇总与落库)."""

    subtask_id: str
    success: bool
    output: str = ""
    error: str | None = None
    latency_ms: float = 0.0
    checkpoint_id: str | None = None
    run_id: int | None = None


async def run_concurrent(
    runners: dict[str, Coroutine[Any, Any, SubtaskResult]],
    timeout: float,
    on_timeout: Callable[[str], SubtaskResult] | None = None,
) -> list[SubtaskResult]:
    """并发执行子任务协程.

    Args:
        runners: subtask_id -> 子任务协程(返回 SubtaskResult).
        timeout: 每个子任务超时秒数(默认 60).
        on_timeout: 超时回调(返回降级结果); None 时用默认超时结果.

    Returns:
        全部子任务结果(顺序与 runners 输入一致), 失败/超时项 success=False.
    """
    if not runners:
        return []

    async def _run_one(subtask_id: str, coro: Coroutine[Any, Any, SubtaskResult]) -> SubtaskResult:
        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(coro, timeout)
            result.latency_ms = round((time.perf_counter() - start) * 1000, 2)
            return result
        except TimeoutError:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning("concurrent.subtask_timeout", subtask_id=subtask_id, timeout=timeout)
            fallback = on_timeout(subtask_id) if on_timeout is not None else None
            return fallback or SubtaskResult(
                subtask_id=subtask_id,
                success=False,
                error=f"子任务超时({timeout}s)",
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.warning("concurrent.subtask_failed", subtask_id=subtask_id, error=str(exc))
            return SubtaskResult(
                subtask_id=subtask_id,
                success=False,
                error=str(exc),
                latency_ms=latency_ms,
            )

    # gather(return_exceptions=True) 双保险: wait_for 已拦截超时, 此处兜底协程异常
    results = await asyncio.gather(
        *(_run_one(sid, coro) for sid, coro in runners.items()), return_exceptions=True
    )
    final: list[SubtaskResult] = []
    for sid, res in zip(runners, results, strict=True):
        if isinstance(res, BaseException):
            logger.error("concurrent.unexpected", subtask_id=sid, error=str(res))
            final.append(SubtaskResult(subtask_id=sid, success=False, error=str(res)))
        else:
            final.append(res)
    return final
