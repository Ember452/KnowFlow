"""报告任务服务单测 - 创建/后台生成/进度查询/发布委托."""

import asyncio
from typing import Any

import pytest

from knowflow.agents.report.models import ReportResult, ReportSpec, ReportStage
from knowflow.services.report_service import ReportService


class _FakePipeline:
    """快速完成的 fake 流水线; error 注入时抛异常."""

    def __init__(self, result: ReportResult | None = None, error: str | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def run(self, query: str, **kwargs: Any) -> ReportResult:
        self.calls.append({"query": query, **kwargs})
        if self._error:
            raise RuntimeError(self._error)
        if self._result is not None:
            if kwargs.get("on_progress") is not None:
                await kwargs["on_progress"](self._result.stage, "完成")
            return self._result
        return ReportResult(run_id="r", spec=ReportSpec(title=query), stage=ReportStage.DONE)


def _result(run_id: str = "r") -> ReportResult:
    return ReportResult(
        run_id=run_id,
        spec=ReportSpec(title="报告"),
        chapters=[],
        review=None,
        markdown_path="/workspace/reports/r.md",
    )


@pytest.mark.asyncio
async def test_create_and_generate_completes() -> None:
    """create 启动后台任务, 完成后状态/产物/进度可查."""
    pipeline = _FakePipeline(result=_result())
    service = ReportService(pipeline=pipeline)

    task = await service.create("总结制度", "u1", session_id=3)
    assert task.status == "running"
    for _ in range(20):  # 等待后台任务完成
        if service.get(task.run_id) is not None and service.get(task.run_id).status != "running":
            break
        await asyncio.sleep(0.01)

    done = service.get(task.run_id)
    assert done is not None
    assert done.status == "completed"
    assert done.stage == ReportStage.DONE.value
    assert service.get_result(task.run_id) is not None
    assert done.result.markdown_path == "/workspace/reports/r.md"
    assert pipeline.calls[0]["query"] == "总结制度"
    assert pipeline.calls[0]["run_id"] == task.run_id


@pytest.mark.asyncio
async def test_create_background_failure_marks_failed() -> None:
    """后台生成异常 → 任务标记 failed 并携带错误."""
    service = ReportService(pipeline=_FakePipeline(error="流水线崩溃"))
    task = await service.create("q", "u1")
    for _ in range(20):
        if service.get(task.run_id) is not None and service.get(task.run_id).status != "running":
            break
        await asyncio.sleep(0.01)
    done = service.get(task.run_id)
    assert done.status == "failed"
    assert "流水线崩溃" in (done.error or "")


@pytest.mark.asyncio
async def test_publish_without_publisher_returns_readable_error() -> None:
    """未注入发布器 → publish 返回可读提示(不抛出)."""
    service = ReportService(pipeline=_FakePipeline(result=_result()))
    task = await service.create("q", "u1")
    for _ in range(20):
        if service.get(task.run_id) is not None and service.get(task.run_id).status != "running":
            break
        await asyncio.sleep(0.01)
    resp = await service.publish(task.run_id)
    assert resp["published"] is False
    assert "未启用" in resp["message"]


@pytest.mark.asyncio
async def test_publish_unknown_or_pending_task() -> None:
    """任务不存在/未完成 → 可读提示."""
    service = ReportService(pipeline=_FakePipeline())
    assert (await service.publish("nope"))["message"] == "报告任务不存在"
    await service.create("q", "u1")  # running 状态
    task = service.get("r")  # 不存在(run_id 是随机生成的)
    assert task is None


@pytest.mark.asyncio
async def test_create_without_pipeline_raises() -> None:
    """流水线不可用 → create 抛 RuntimeError."""
    service = ReportService(pipeline=None)
    with pytest.raises(RuntimeError, match="不可用"):
        await service.create("q", "u1")


def test_get_missing_returns_none() -> None:
    """不存在的任务返回 None."""
    service = ReportService(pipeline=_FakePipeline())
    assert service.get("missing") is None
    assert service.get_result("missing") is None
