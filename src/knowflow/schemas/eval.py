"""评测 Schema - 评测任务/结果.

M3 仅定义 Schema 与路由占位, 离线评测在 P10(M8) 实现.
对齐 models/eval.py: EvalDataset/EvalRun/EvalResult.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class EvalRunInfo(BaseModel):
    """评测运行记录."""

    id: int
    dataset_id: int
    status: str = Field(description="pending/running/completed/failed")
    metrics: dict | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class EvalRunRequest(BaseModel):
    """启动评测请求."""

    dataset_id: int
    mode: str = Field(default="graphrag", description="baseline/graphrag 对比模式")
