"""通用响应 Schema - 统一响应信封与分页结构.

所有 API 响应遵循 `{code, message, data}` 信封, 便于客户端程序化处理.
分页响应统一为 `{items, total, limit, offset}`.
"""

from pydantic import BaseModel, Field


class ApiResponse[T](BaseModel):
    """统一响应信封."""

    code: str = Field(default="ok", description="业务状态码, ok 表示成功, 否则为错误码")
    message: str = Field(default="ok", description="面向用户的可读消息")
    data: T | None = Field(default=None, description="响应数据")


class PageResponse[T](BaseModel):
    """分页响应."""

    items: list[T] = Field(default_factory=list, description="当页数据")
    total: int = Field(default=0, description="总条数")
    limit: int = Field(default=50, description="每页条数")
    offset: int = Field(default=0, description="偏移量")


class ErrorResponse(BaseModel):
    """错误响应."""

    code: str = Field(description="错误码, 如 APP-001")
    message: str = Field(description="错误消息")
    details: dict[str, object] = Field(default_factory=dict, description="附加上下文")


def ok(data: object = None, message: str = "ok") -> dict[str, object]:
    """构造成功响应 dict(供 endpoint 直接 return)."""
    return {"code": "ok", "message": message, "data": data}
