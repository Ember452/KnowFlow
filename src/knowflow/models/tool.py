"""工具治理模型. ToolCall / SkillActivation / ToolMetric."""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, JSONBType, TimestampMixin


class ToolCall(Base, IDMixin, TimestampMixin):
    """工具调用记录. 每次工具执行落一条, 用于 trace 与指标统计."""

    __tablename__ = "tool_calls"

    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    agent_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_usage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("idx_tool_calls_session", "session_id"),)


class SkillActivation(Base, IDMixin, TimestampMixin):
    """Skill 激活记录. 跟踪每个会话中 Skill 的启停."""

    __tablename__ = "skill_activations"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("idx_skill_act_session", "session_id"),
        Index("idx_skill_act_name", "skill_name"),
    )


class ToolMetric(Base, IDMixin, TimestampMixin):
    """工具治理指标快照. 可见工具数 / Schema Token / FC 准确率统计."""

    __tablename__ = "tool_metrics"

    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    visible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fc_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scenario: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="指标场景")

    __table_args__ = (Index("idx_tool_metrics_name", "tool_name"),)
