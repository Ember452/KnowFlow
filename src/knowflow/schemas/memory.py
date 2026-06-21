"""记忆 Schema - 长期记忆条目.

M3 仅定义 Schema 与路由占位, 记忆模块在 P7(M6) 实现.
对齐 models/memory.py: LongTermMemory(user_id/session_id/content/summary/importance).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    """长期记忆条目."""

    id: int
    user_id: str
    session_id: int
    content: str
    summary: str | None = None
    importance: float = 0.0
    created_at: datetime | None = None
    last_recall: datetime | None = None


class MemoryRecallRequest(BaseModel):
    """记忆召回请求."""

    query: str = Field(min_length=1, max_length=2000)
    user_id: str
    top_k: int = Field(default=5, ge=1, le=20)


class MemorySedimentRequest(BaseModel):
    """手动沉淀请求: 将指定会话的短期记忆筛选压缩后写入长期."""

    session_id: int
