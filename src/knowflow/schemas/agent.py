"""Agent 编排 Schema - AgentRun/委派信息.

M3 仅定义 Schema 与路由占位, 编排在 P8(M7) 实现.
字段对齐 models/agent.py: AgentRun/TaskDelegation/Checkpoint.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentRunInfo(BaseModel):
    """Agent 运行记录."""

    id: int
    session_id: int
    parent_run_id: int | None = None
    status: str
    input: dict | None = None
    output: dict | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class TaskDelegationInfo(BaseModel):
    """任务委派记录."""

    id: int
    parent_run_id: int
    sub_run_id: int | None = None
    description: str
    status: str = Field(description="created/delegated/running/completed/failed")
    result: dict | None = None
    checkpoint_id: int | None = None
