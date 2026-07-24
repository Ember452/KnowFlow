"""记忆模型. LongTermMemory / MemorySummary / MemoryConflict.

与设计文档 3.4 模块六一致, long_term_memories 表用 created_at/last_recall(无 updated_at).
embedding 字段 P2 用 LargeBinary, P7 评估迁移 pgvector VECTOR(1024).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, TimestampMixin, VectorField


class LongTermMemory(Base, IDMixin):
    """长期记忆. 跨会话持久化, 按相关度+时间衰减召回."""

    __tablename__ = "long_term_memories"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="压缩后内容")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False, comment="0-10 重要性分数")
    # P2 用 LargeBinary 存序列化向量, P7 评估迁移 pgvector VECTOR(1024)
    embedding: Mapped[bytes | None] = mapped_column(VectorField, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_recall: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最近召回时间(衰减用)"
    )

    __table_args__ = (
        Index("idx_memories_user", "user_id"),
        Index("idx_memories_importance", "importance"),
    )


class MemorySummary(Base, IDMixin, TimestampMixin):
    """记忆摘要. 用户/会话级的记忆压缩结果."""

    __tablename__ = "memory_summaries"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("idx_memory_summaries_user", "user_id"),)


class MemoryConflict(Base, IDMixin):
    """记忆冲突记录. 新记忆与存量记忆语义矛盾时留痕(供审查/仲裁).

    status: pending(待处理) / resolved(已处理). 新记忆照常生效, 冲突记录供人工审查.
    """

    __tablename__ = "memory_conflicts"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    new_content: Mapped[str] = mapped_column(Text, nullable=False, comment="新记忆内容")
    old_memory_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("long_term_memories.id", ondelete="SET NULL"), nullable=True
    )
    old_content: Mapped[str] = mapped_column(Text, nullable=False, comment="存量记忆内容")
    reason: Mapped[str] = mapped_column(String(255), nullable=False, comment="冲突判定原因")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", comment="pending/resolved"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_memory_conflicts_user", "user_id"),
        Index("idx_memory_conflicts_status", "status"),
    )
