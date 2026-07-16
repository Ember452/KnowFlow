"""对话 Schema - 对话请求/响应/引用.

M3 仅定义 Schema 与路由占位, 对话主流程在 P5(M4) 实现.
字段对齐 models/session.py: Message(role/content/tokens/citations), citations 为
chunk_id 列表 + 工具调用的 JSON.
"""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """检索引用(含文档出处)."""

    chunk_id: int
    content: str | None = None
    score: float | None = None
    source: str | None = None
    doc_id: int | None = None
    doc_title: str | None = None


class ChatRequest(BaseModel):
    """对话请求."""

    session_id: str | None = Field(default=None, description="会话 id; 为空则新建会话")
    message: str = Field(min_length=1, max_length=8000, description="用户消息")
    user_id: str | None = Field(default=None, description="用户标识, 新建会话时使用")
    stream: bool = Field(default=False, description="是否流式(SSE)")


class ChatResponse(BaseModel):
    """同步对话响应."""

    session_id: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    tool_calls: list[dict] = Field(
        default_factory=list, description="本轮工具调用记录(名称/参数/成败/耗时)"
    )
    latency_ms: float = 0.0
