"""评测端点 - 触发静态评测并落库 / 查询评测结果(P10/M8 实现).

POST /eval/run        触发一次评测(静态模式, 可复现; 真实模式需外部依赖)
GET  /eval/runs/{run_id}  查询评测结果(汇总指标 + 逐条结果)
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from knowflow.api.deps import DbDep
from knowflow.models.eval import EvalDataset as EvalDatasetModel
from knowflow.models.eval import EvalResult, EvalRun
from knowflow.observability.eval.dataset import EvalDataset
from knowflow.observability.eval.runner import EvalRunner
from knowflow.observability.eval.static import FakeLLM, FakeRetriever

router = APIRouter(prefix="/eval", tags=["eval"])

# 项目根: src/knowflow/api/v1/endpoints/eval.py → parents[5] = 仓库根
ROOT = Path(__file__).resolve().parents[5]
RETRIEVAL_EVAL = ROOT / "eval" / "datasets" / "retrieval_eval.jsonl"
QA_EVAL = ROOT / "eval" / "datasets" / "knowledge_qa_eval.jsonl"
CHUNK_MAP_FILE = ROOT / "eval" / "datasets" / "chunk_id_map.json"


class EvalRunRequest(BaseModel):
    """评测运行请求."""

    dataset: str = Field(default="retrieval_eval", description="retrieval_eval / knowledge_qa_eval")
    mode: str = Field(default="static", description="static / real(需外部依赖)")
    top_k: int = Field(default=10, ge=1, le=50)


class EvalRunInfo(BaseModel):
    """评测运行结果."""

    run_id: int
    dataset: str
    status: str
    summary: dict[str, float]
    results: list[dict[str, Any]]


async def _run_static_eval(dataset: str, top_k: int) -> dict[str, Any]:
    """静态评测: fake 组件 + 真实评测流程(可复现)."""
    runner = EvalRunner(
        FakeRetriever(CHUNK_MAP_FILE),
        FakeLLM(),
        chunk_map=EvalRunner.load_chunk_map(CHUNK_MAP_FILE),
    )
    if dataset == "retrieval_eval":
        result = await runner.run_retrieval(EvalDataset.load(RETRIEVAL_EVAL), top_k=top_k)
        summary = {k: round(v, 4) for k, v in result["summary"].items()}
        details = [
            {"query": d["query"], "recall@10": d["recall@10"], "mrr": d["mrr"]}
            for d in result["details"]
        ]
    else:
        result = await runner.run_qa(EvalDataset.load(QA_EVAL, kind="knowledge_qa"), top_k=5)
        summary = {"keypoint_hit_rate": round(result["summary"]["keypoint_hit_rate"], 4)}
        details = [
            {"query": d["query"], "keypoint_hit_rate": d["keypoint_hit_rate"]}
            for d in result["details"]
        ]
    return {"summary": summary, "details": details}


@router.post("/run", response_model=EvalRunInfo)
async def run_eval(req: EvalRunRequest, db: DbDep) -> EvalRunInfo:
    """触发一次评测: 结果落库 eval_runs/eval_results."""
    if req.dataset not in ("retrieval_eval", "knowledge_qa_eval"):
        raise HTTPException(status_code=400, detail=f"未知评测集: {req.dataset}")
    if req.mode != "static":
        # 真实模式需完整外部依赖, 指引走离线脚本
        raise HTTPException(
            status_code=400, detail="真实模式请用 eval/scripts/run_eval.py --mode real"
        )

    # 数据集记录(不存在则创建, 满足外键约束)
    ds_row = await db.scalar(select(EvalDatasetModel).where(EvalDatasetModel.name == req.dataset))
    if ds_row is None:
        ds_row = EvalDatasetModel(name=req.dataset, description="静态评测", item_count=0)
        db.add(ds_row)
        await db.flush()
        await db.refresh(ds_row)

    run_row = EvalRun(
        dataset_id=int(ds_row.id),
        status="running",
        config={"dataset": req.dataset, "mode": req.mode},
    )
    db.add(run_row)
    await db.flush()
    await db.refresh(run_row)

    try:
        result = await _run_static_eval(req.dataset, req.top_k)
        run_row.status = "completed"
        run_row.started_at = datetime.now(UTC)
        run_row.completed_at = datetime.now(UTC)
        run_row.summary = result["summary"]
        for detail in result["details"]:
            db.add(
                EvalResult(
                    run_id=int(run_row.id),
                    query=detail["query"],
                    expected={},
                    actual={},
                    metrics=detail,
                )
            )
        await db.commit()
    except Exception as exc:
        run_row.status = "failed"
        run_row.completed_at = datetime.now(UTC)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"评测执行失败: {exc}") from exc

    return EvalRunInfo(
        run_id=int(run_row.id),
        dataset=req.dataset,
        status=run_row.status,
        summary=result["summary"],
        results=result["details"],
    )


@router.get("/runs/{run_id}", response_model=EvalRunInfo)
async def get_eval_run(run_id: int, db: DbDep) -> EvalRunInfo:
    """查询评测结果(汇总指标 + 逐条结果)."""
    run_row = await db.get(EvalRun, run_id)
    if run_row is None:
        raise HTTPException(status_code=404, detail=f"评测运行不存在: run_id={run_id}")
    stmt = select(EvalResult).where(EvalResult.run_id == run_id).order_by(EvalResult.id.asc())
    rows = (await db.execute(stmt)).scalars().all()
    config = run_row.config or {}
    return EvalRunInfo(
        run_id=run_id,
        dataset=str(config.get("dataset", "unknown")),
        status=run_row.status,
        summary=run_row.summary or {},
        results=[r.metrics or {} for r in rows],
    )
