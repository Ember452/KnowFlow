"""Agent 编排 Schema - AgentRun/委派/Checkpoint 信息.

P8(M7) 实现: 字段对齐 models/agent.py(AgentRun/TaskDelegation),
checkpoint 信息由 agents/checkpoint.py 的 lineage 提供(LangGraph 原生表).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentRunInfo(BaseModel):
    """Agent 运行记录."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    agent_type: str = Field(description="main/sub")
    parent_run_id: int | None = None
    status: str = Field(description="running/completed/failed")
    started_at: datetime
    completed_at: datetime | None = None


class TaskDelegationInfo(BaseModel):
    """任务委派记录."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_run_id: int
    child_run_id: int | None = None
    task: str
    status: str = Field(description="created/delegated/running/completed/failed")
    result: dict | None = None
    checkpoint_id: str | None = None
    created_at: datetime


class AgentRunDetail(BaseModel):
    """Agent 运行详情: 父子 run 记录 + 委派链."""

    run: AgentRunInfo
    children: list[AgentRunInfo] = Field(default_factory=list)
    delegations: list[TaskDelegationInfo] = Field(default_factory=list)
