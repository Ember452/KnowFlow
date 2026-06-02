"""统一异常体系. AppError 基类携带 error_code + status_code, 便于 API 层统一转换."""

from typing import Any


class AppError(Exception):
    """应用异常基类.

    Attributes:
        error_code: 稳定错误码, 前缀标识模块(如 RETR-001), 供客户端程序化处理.
        message: 面向用户的可读消息.
        status_code: HTTP 状态码.
        details: 附加上下文(可选), 会被序列化进响应.
    """

    error_code: str = "APP-000"
    status_code: int = 500
    default_message: str = "内部错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if error_code is not None:
            self.error_code = error_code
        if status_code is not None:
            self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """转换为响应字典, 供 API 层统一错误响应使用."""
        return {
            "code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class NotFoundError(AppError):
    """资源不存在."""

    error_code = "APP-001"
    status_code = 404
    default_message = "资源不存在"


class PermissionDeniedError(AppError):
    """权限不足或执行域越权."""

    error_code = "APP-002"
    status_code = 403
    default_message = "权限不足"


class ToolExecutionError(AppError):
    """工具执行失败."""

    error_code = "TOOL-001"
    status_code = 500
    default_message = "工具执行失败"


class RateLimitError(AppError):
    """触发限流."""

    error_code = "APP-003"
    status_code = 429
    default_message = "请求过于频繁"


class ContextOverflowError(AppError):
    """上下文超预算且无法降级."""

    error_code = "CTX-001"
    status_code = 500
    default_message = "上下文超预算"


class ValidationError(AppError):
    """业务校验失败(非 pydantic 校验)."""

    error_code = "APP-004"
    status_code = 422
    default_message = "参数校验失败"


class ExternalServiceError(AppError):
    """外部依赖(LLM/向量库等)调用失败."""

    error_code = "APP-005"
    status_code = 502
    default_message = "外部服务调用失败"
