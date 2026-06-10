"""文档相关 Schema - 上传响应/文档信息/列表/重建索引.

字段对齐 models/document.py: Document(title/source_uri/file_type/status/content_hash/
size_bytes/user_id/error_message + id/created_at/updated_at).
"""

from datetime import datetime

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """文档上传响应."""

    doc_id: int = Field(description="文档 id")
    title: str = Field(description="文档标题")
    status: str = Field(description="索引状态: pending/indexing/ready/failed")
    duplicated: bool = Field(default=False, description="是否命中秒传去重")
    message: str = Field(default="已接收, 等待索引")


class DocumentInfo(BaseModel):
    """文档元信息."""

    id: int
    title: str
    file_type: str
    status: str
    size_bytes: int
    content_hash: str | None = None
    user_id: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReindexResponse(BaseModel):
    """重建索引响应."""

    doc_id: int
    status: str = Field(description="重新置为 pending, 等待 worker 消费")
    message: str = "已投递重建索引任务"


class DeleteResponse(BaseModel):
    """删除文档响应."""

    doc_id: int
    deleted: bool
    message: str = "已删除"
