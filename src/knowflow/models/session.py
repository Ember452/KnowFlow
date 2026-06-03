"""会话模型. Session / Message / Turn - 对话历史存储."""

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, JSONBType, TimestampMixin


class Session(Base, IDMixin, TimestampMixin):
    """对话会话."""

    __tablename__ = "sessions"

    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    __table_args__ = (Index("idx_sessions_user", "user_id"),)


class Message(Base, IDMixin, TimestampMixin):
    """单条消息. role: user/assistant/system/tool."""

    __tablename__ = "messages"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 关联的检索引用(chunk_id 列表)与工具调用, 用 JSON 存
    citations: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)

    __table_args__ = (Index("idx_messages_session", "session_id"),)


class Turn(Base, IDMixin, TimestampMixin):
    """对话轮次. 一次 user + assistant 交互为一个 turn."""

    __tablename__ = "turns"

    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    user_message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    assistant_message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("idx_turns_session", "session_id"),)
