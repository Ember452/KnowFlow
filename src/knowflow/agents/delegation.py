"""TaskDelegation 协议 - 主 Agent 委派子任务的状态机封装.

状态机: created → delegated → running → completed / failed.
状态落 task_delegations 表(与 AgentRun/TaskDelegation repo 同一事务).
"""

from typing import Any

from knowflow.core.constants import DelegationStatus
from knowflow.core.logging import get_logger
from knowflow.db.repositories.agent_repo import TaskDelegationRepo

logger = get_logger(__name__)

# 合法状态转换表: 当前状态 -> 允许的下一状态集合
_TRANSITIONS: dict[str, set[str]] = {
    DelegationStatus.CREATED: {DelegationStatus.DELEGATED, DelegationStatus.RUNNING},
    DelegationStatus.DELEGATED: {DelegationStatus.RUNNING, DelegationStatus.FAILED},
    DelegationStatus.RUNNING: {DelegationStatus.COMPLETED, DelegationStatus.FAILED},
    DelegationStatus.COMPLETED: set(),
    DelegationStatus.FAILED: set(),
}


class TaskDelegation:
    """委派协议对象. 持有 repo 与 delegation_id, 只暴露状态机方法.

    由 TaskDelegationFactory.create() 创建(落库)后使用; 每次转换立即 flush,
    与调用方事务同批提交.
    """

    def __init__(self, repo: TaskDelegationRepo, delegation_id: int, task: str) -> None:
        self._repo = repo
        self.delegation_id = delegation_id
        self.task = task
        self._status: str = DelegationStatus.CREATED

    @property
    def status(self) -> str:
        """当前状态."""
        return self._status

    def _transition(self, target: str) -> None:
        """校验并推进状态机."""
        allowed = _TRANSITIONS.get(self._status, set())
        if target not in allowed:
            logger.warning(
                "task_delegation.illegal_transition",
                delegation_id=self.delegation_id,
                current=self._status,
                target=target,
            )
            raise ValueError(
                f"非法委派状态转换: {self._status} -> {target} (delegation_id={self.delegation_id})"
            )
        self._status = target

    async def mark_delegated(self, child_run_id: int) -> None:
        """委派给子 Agent(记录 child_run_id)."""
        self._transition(DelegationStatus.DELEGATED)
        await self._repo.update_status(
            self.delegation_id, DelegationStatus.DELEGATED, child_run_id=child_run_id
        )

    async def mark_running(self) -> None:
        """子 Agent 开始执行."""
        self._transition(DelegationStatus.RUNNING)
        await self._repo.update_status(self.delegation_id, DelegationStatus.RUNNING)

    async def complete(self, result: dict[str, Any], checkpoint_id: str | None = None) -> None:
        """子 Agent 执行成功."""
        self._transition(DelegationStatus.COMPLETED)
        await self._repo.update_status(
            self.delegation_id,
            DelegationStatus.COMPLETED,
            result=result,
            checkpoint_id=checkpoint_id,
        )

    async def fail(self, error: str) -> None:
        """子 Agent 执行失败(降级, 不阻塞整体)."""
        self._transition(DelegationStatus.FAILED)
        await self._repo.update_status(
            self.delegation_id, DelegationStatus.FAILED, result={"error": error}
        )


class TaskDelegationFactory:
    """创建 TaskDelegation 协议对象(状态机起点 created)."""

    def __init__(self, repo: TaskDelegationRepo) -> None:
        self._repo = repo

    async def create(self, parent_run_id: int, task: str) -> TaskDelegation:
        """落库创建委派记录, 返回协议对象."""
        delegation = await self._repo.create(parent_run_id=parent_run_id, task=task)
        return TaskDelegation(self._repo, int(delegation.id), task)
