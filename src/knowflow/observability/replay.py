"""Replayer - 按 checkpoint + trace 重放会话.

重放 = 恢复状态(CheckpointManager.restore) + 按时间序重放已记录事件(TraceStore),
不执行任何 LLM 调用. 用于"断点续跑演示"与"事故复盘"的可视化.
thread_id 约定为 str(agent_run_id)(与 orchestrator 一致), 取该会话主 run 的线程.
"""

from __future__ import annotations

from typing import Any

from knowflow.agents.checkpoint import CheckpointManager
from knowflow.core.logging import get_logger
from knowflow.db.repositories.agent_repo import AgentRunRepo
from knowflow.db.repositories.trace_repo import TraceSpanRepo
from knowflow.observability.store import TraceStore

logger = get_logger(__name__)


class Replayer:
    """会话重放器: 恢复状态 + 时间序事件流."""

    def __init__(self, checkpoints: CheckpointManager, store: TraceStore) -> None:
        self._checkpoints = checkpoints
        self._store = store

    async def replay(
        self,
        session_id: int,
        checkpoint_id: str | None = None,
    ) -> dict[str, Any]:
        """重放会话.

        Args:
            session_id: 目标会话.
            checkpoint_id: 指定恢复点; None 时取线程最新.

        Returns:
            {"session_id", "run_id", "checkpoint_id", "state", "events"}:
            state 为恢复的 AgentState; events 为按时间序的 span 快照列表.
        """
        # 1. 定位该会话主 run(thread_id = str(run_id))
        runs = await AgentRunRepo(self._store.session).list_by_session(session_id)
        main_runs = [r for r in runs if r.agent_type == "main"]
        if not main_runs:
            raise ValueError(f"会话 {session_id} 无主 Agent run, 无法重放")
        run_id = int(main_runs[-1].id)
        thread_id = str(run_id)

        # 2. 恢复 checkpoint 状态(缺省取线程最新)
        state = await self._checkpoints.restore(thread_id, checkpoint_id)
        if state is None:
            raise ValueError(f"线程 {thread_id} 无 checkpoint 可恢复")
        used_checkpoint = checkpoint_id
        if used_checkpoint is None:
            chain = await self._checkpoints.lineage(thread_id)
            used_checkpoint = chain[0]["checkpoint_id"] if chain else None

        # 3. 按时间序重放该会话全部 span 快照
        spans = await TraceSpanRepo(self._store.session).list_by_session(session_id)
        events = [
            {
                "ts": spn.started_at.isoformat(),
                "span_id": int(spn.id),
                "parent_span_id": int(spn.parent_span_id) if spn.parent_span_id else None,
                "span_type": spn.span_type,
                "name": spn.name,
                "input": spn.input,
                "output": spn.output,
                "ended_at": spn.ended_at.isoformat() if spn.ended_at else None,
            }
            for spn in spans
        ]
        logger.info("replay.completed", session_id=session_id, run_id=run_id, events=len(events))
        return {
            "session_id": session_id,
            "run_id": run_id,
            "checkpoint_id": used_checkpoint,
            "state": state,
            "events": events,
        }
