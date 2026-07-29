"""报告任务服务 - 进程内任务注册表(MVP 不落库) + 后台生成 + 发布委托.

create 启动后台任务(asyncio.create_task), get/get_result 查询进度与产物;
publish 委托 ReportPublisher(飞书 MCP 发布, 未注入时返回"发布能力未启用").
任务状态 MVP 不落库, 断点续跑为 M3 打磨项(复用 checkpoint 时引入).
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from knowflow.agents.report.models import ReportResult, ReportStage
from knowflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ReportTask:
    """报告任务运行时状态."""

    run_id: str
    query: str
    user_id: str
    session_id: int | str | None = None
    status: str = "running"  # running / completed / failed
    stage: str = ReportStage.PLANNING.value
    detail: str = "任务已创建"
    error: str | None = None
    result: ReportResult | None = None
    progress_log: list[dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None


class ReportService:
    """报告任务服务: 创建/进度/产物/发布."""

    def __init__(self, pipeline: Any | None = None, publisher: Any | None = None) -> None:
        self._pipeline = pipeline  # ReportPipeline; None 时 create 报"不可用"
        self._publisher = publisher  # ReportPublisher; None 时 publish 报"未启用"
        self._tasks: dict[str, ReportTask] = {}
        self._bg_tasks: set[asyncio.Task[Any]] = set()  # 后台生成任务句柄(防 GC)

    @property
    def pipeline(self) -> Any | None:
        """报告流水线(评测脚本等只读访问)."""
        return self._pipeline

    @property
    def publisher(self) -> Any | None:
        """报告发布器(只读)."""
        return self._publisher

    async def create(
        self,
        query: str,
        user_id: str,
        session_id: int | str | None = None,
    ) -> ReportTask:
        """创建报告任务并启动后台生成; 返回任务(含 run_id)."""
        if self._pipeline is None:
            raise RuntimeError("报告流水线不可用(依赖未就绪)")
        task = ReportTask(
            run_id=uuid4().hex[:12],
            query=query,
            user_id=user_id,
            session_id=session_id,
        )
        self._tasks[task.run_id] = task
        bg = asyncio.create_task(self._generate(task))
        self._bg_tasks.add(bg)
        bg.add_done_callback(self._bg_tasks.discard)
        return task

    def get(self, run_id: str) -> ReportTask | None:
        """查询任务; 不存在返回 None."""
        return self._tasks.get(run_id)

    def get_result(self, run_id: str) -> ReportResult | None:
        """查询任务产物; 不存在/未完成返回 None."""
        task = self._tasks.get(run_id)
        return task.result if task is not None else None

    async def publish(self, run_id: str) -> dict[str, Any]:
        """发布报告(委托 publisher); 未启用/前置不满足返回可读错误(不抛出)."""
        task = self._tasks.get(run_id)
        if task is None:
            return {"published": False, "message": "报告任务不存在"}
        if task.result is None or task.status != "completed":
            return {"published": False, "message": "报告尚未生成完成"}
        if self._publisher is None:
            return {"published": False, "message": "发布能力未启用(飞书 MCP 未接入)"}
        resp: dict[str, Any] = await self._publisher.publish(task.result)
        return resp

    async def _generate(self, task: ReportTask) -> None:
        """后台执行流水线; 进度经回调同步到任务状态."""
        assert self._pipeline is not None  # create 时已校验非 None
        try:

            async def on_progress(stage: Any, detail: str) -> None:
                stage_val = stage.value if hasattr(stage, "value") else str(stage)
                task.stage = stage_val
                task.detail = detail
                task.progress_log.append(
                    {
                        "stage": stage_val,
                        "detail": detail,
                        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                    }
                )

            result = await self._pipeline.run(
                task.query,
                user_id=task.user_id,
                session_id=task.session_id,
                run_id=task.run_id,
                on_progress=on_progress,
            )
            task.result = result
            if result.stage == ReportStage.FAILED or result.error:
                task.status = "failed"
                task.error = result.error or "流水线执行失败"
            else:
                task.status = "completed"
                task.stage = ReportStage.DONE.value
                task.detail = f"完成, 落盘: {result.markdown_path or '(未落盘)'}"
        except Exception as exc:
            logger.error("report.task_failed", run_id=task.run_id, error=str(exc))
            task.status = "failed"
            task.error = str(exc)
        finally:
            task.completed_at = datetime.now(UTC)
