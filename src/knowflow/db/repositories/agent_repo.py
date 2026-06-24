"""AgentRun / TaskDelegation 数据访问层.

checkpoint 由 LangGraph PostgresSaver 原生表接管(见 docs/adr/0004),
lineage 查询在 agents/checkpoint.py 的 CheckpointManager 中实现.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.models.agent import AgentRun, TaskDelegation


class AgentRunRepo:
    """Agent 运行实例 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: int,
        agent_type: str,
        parent_run_id: int | None = None,
        status: str = "running",
    ) -> AgentRun:
        """新建 Agent 运行. agent_type: main/sub."""
        run = AgentRun(
            session_id=session_id,
            agent_type=agent_type,
            parent_run_id=parent_run_id,
            status=status,
        )
        self.session.add(run)
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: int) -> AgentRun | None:
        """按主键查运行实例."""
        return await self.session.get(AgentRun, run_id)

    async def list_by_session(self, session_id: int) -> Sequence[AgentRun]:
        """按会话列出全部运行实例, 按 id 升序."""
        stmt = select(AgentRun).where(AgentRun.session_id == session_id).order_by(AgentRun.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_children(self, parent_run_id: int) -> Sequence[AgentRun]:
        """列出某主 Agent 的子运行(委派出去的子 Agent)."""
        stmt = (
            select(AgentRun)
            .where(AgentRun.parent_run_id == parent_run_id)
            .order_by(AgentRun.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def mark_completed(
        self,
        run_id: int,
        status: str = "completed",
        completed_at: datetime | None = None,
    ) -> bool:
        """标记运行完成(completed/failed). 返回是否命中.

        completed_at 由 service 层传入 datetime, 缺省不更新该字段.
        """
        run = await self.get(run_id)
        if run is None:
            return False
        run.status = status
        if completed_at is not None:
            run.completed_at = completed_at
        await self.session.flush()
        return True


class TaskDelegationRepo:
    """任务委派记录 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        parent_run_id: int,
        task: str,
        child_run_id: int | None = None,
        status: str = "created",
        checkpoint_id: str | None = None,
    ) -> TaskDelegation:
        """新建委派记录."""
        delegation = TaskDelegation(
            parent_run_id=parent_run_id,
            task=task,
            child_run_id=child_run_id,
            status=status,
            checkpoint_id=checkpoint_id,
        )
        self.session.add(delegation)
        await self.session.flush()
        await self.session.refresh(delegation)
        return delegation

    async def get(self, delegation_id: int) -> TaskDelegation | None:
        """按主键查委派."""
        return await self.session.get(TaskDelegation, delegation_id)

    async def list_by_parent(self, parent_run_id: int) -> Sequence[TaskDelegation]:
        """按父运行列出委派."""
        stmt = (
            select(TaskDelegation)
            .where(TaskDelegation.parent_run_id == parent_run_id)
            .order_by(TaskDelegation.id.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_status(
        self,
        delegation_id: int,
        status: str,
        result: dict | None = None,
        checkpoint_id: str | None = None,
        child_run_id: int | None = None,
    ) -> bool:
        """更新委派状态与结果. 返回是否命中."""
        delegation = await self.get(delegation_id)
        if delegation is None:
            return False
        delegation.status = status
        if result is not None:
            delegation.result = result
        if checkpoint_id is not None:
            delegation.checkpoint_id = checkpoint_id
        if child_run_id is not None:
            delegation.child_run_id = child_run_id
        await self.session.flush()
        return True
