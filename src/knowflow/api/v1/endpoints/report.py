"""报告端点 - 报告任务创建/进度/产物/发布.

POST /reports 创建报告任务(后台生成, 阶段进度见 GET /reports/{id});
GET /reports/{id}/result 返回完整产物(spec/evidence/chapters/references);
POST /reports/{id}/publish 发布到飞书云文档(依赖 MCP 接入, 未启用时返回可读降级提示).
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from knowflow.api.deps import ReportServiceDep, UserDep
from knowflow.schemas.common import ApiResponse
from knowflow.schemas.report import (
    ChapterOut,
    EvidenceOut,
    PublishResultOut,
    ReportCreateRequest,
    ReportOut,
    ReportResultOut,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("", response_model=ApiResponse[ReportOut])
async def create_report(
    req: ReportCreateRequest,
    user_id: UserDep,
    service: ReportServiceDep,
) -> ApiResponse[ReportOut]:
    """创建报告任务并启动后台生成."""
    if service is None:
        raise HTTPException(status_code=503, detail="报告服务不可用(依赖未就绪)")
    try:
        task = await service.create(req.query, user_id, req.session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ApiResponse(data=_to_report_out(task))


@router.get("/{run_id}", response_model=ApiResponse[ReportOut])
async def get_report(run_id: str, service: ReportServiceDep) -> ApiResponse[ReportOut]:
    """查询报告任务状态与阶段进度."""
    if service is None:
        raise HTTPException(status_code=503, detail="报告服务不可用(依赖未就绪)")
    task = service.get(run_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"报告任务不存在: {run_id}")
    return ApiResponse(data=_to_report_out(task))


@router.get("/{run_id}/result", response_model=ApiResponse[ReportResultOut])
async def get_report_result(run_id: str, service: ReportServiceDep) -> ApiResponse[ReportResultOut]:
    """查询报告产物(spec/evidence/chapters/references)."""
    if service is None:
        raise HTTPException(status_code=503, detail="报告服务不可用(依赖未就绪)")
    task = service.get(run_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"报告任务不存在: {run_id}")
    if task.result is None:
        raise HTTPException(status_code=409, detail="报告尚未生成完成")
    result = task.result
    return ApiResponse(
        data=ReportResultOut(
            run_id=result.run_id,
            title=result.spec.title,
            status=task.status,
            chapters=[ChapterOut(title=c.title, body=c.body) for c in result.chapters],
            evidence=[
                EvidenceOut(
                    source=e.source.value,
                    content=e.content,
                    title=e.title,
                    doc_id=e.doc_id,
                    url=e.url,
                )
                for e in result.evidence
            ],
            references=result.references,
            review_passed=bool(result.review and result.review.passed),
            issues=list(result.review.issues) if result.review else [],
            markdown_path=result.markdown_path,
        )
    )


@router.post("/{run_id}/publish", response_model=ApiResponse[PublishResultOut])
async def publish_report(run_id: str, service: ReportServiceDep) -> ApiResponse[PublishResultOut]:
    """发布报告到飞书云文档; 未启用/失败返回可读降级提示(不抛异常)."""
    if service is None:
        raise HTTPException(status_code=503, detail="报告服务不可用(依赖未就绪)")
    result = await service.publish(run_id)
    return ApiResponse(
        data=PublishResultOut(
            run_id=run_id,
            published=bool(result.get("published")),
            doc_url=str(result.get("doc_url", "")),
            message=str(result.get("message", "")),
        )
    )


def _to_report_out(task: Any) -> ReportOut:
    """任务 → 状态 DTO."""
    return ReportOut(
        run_id=task.run_id,
        query=task.query,
        status=task.status,
        stage=task.stage,
        detail=task.detail,
        error=task.error,
        markdown_path=task.result.markdown_path if task.result else "",
        progress_log=task.progress_log,
    )
