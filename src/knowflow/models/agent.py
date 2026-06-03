"""Agent 编排模型. AgentRun / TaskDelegation / Checkpoint.

与设计文档 3.4 模块三一致, 这三张表用 started_at/completed_at/created_at.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, JSONBType


class AgentRun(Base, IDMixin):
    """Agent 运行实例. main/sub 通过 agent_type 区分, parent_run_id 记录父子."""

    __tablename__ = "agent_runs"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    agent_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="main/sub")
    parent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("idx_agent_runs_session", "session_id"),)


class TaskDelegation(Base, IDMixin):
    """任务委派记录. 主 Agent 委派给子 Agent 的任务及其状态."""

    __tablename__ = "task_delegations"

    parent_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    child_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    result: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_delegations_parent", "parent_run_id"),)


class Checkpoint(Base):
    """LangGraph checkpoint. P8 接 PostgresSaver, 此处先建表对齐设计."""

    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, comment="UUID")
    agent_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    parent_checkpoint_id: Mapped[str | None] = mapped_column(
        String(128), ForeignKey("checkpoints.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[dict] = mapped_column(JSONBType, nullable=False, comment="序列化 AgentState")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_checkpoints_run", "agent_run_id"),)
