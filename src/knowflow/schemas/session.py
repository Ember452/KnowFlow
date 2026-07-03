"""会话历史 Schema - 会话列表与消息明细(只读查询响应).

字段对齐 models/session.py: Session(id/user_id/title/status/created_at/updated_at),
Message(id/session_id/role/content/tokens/citations/created_at).
"""

from datetime import datetime

from pydantic import BaseModel


class SessionOut(BaseModel):
    """会话列表项."""

    id: int
    user_id: str | None = None
    title: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MessageOut(BaseModel):
    """消息明细项."""

    id: int
    session_id: int
    role: str
    content: str
    tokens: int = 0
    citations: dict | None = None
    created_at: datetime | None = None
