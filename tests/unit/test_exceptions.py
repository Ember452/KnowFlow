"""异常体系单测 - 验证 error_code / status_code / to_dict 行为."""

import pytest

from knowflow.core.exceptions import (
    AppError,
    ContextOverflowError,
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ToolExecutionError,
    ValidationError,
)


def test_app_error_defaults() -> None:
    """基类应有默认 error_code 与 status_code."""
    e = AppError()
    assert e.error_code == "APP-000"
    assert e.status_code == 500
    assert e.message == "内部错误"
    assert e.details == {}


def test_app_error_custom() -> None:
    """自定义 message / error_code / status_code / details 应被正确存储."""
    e = AppError(
        "custom",
        error_code="X-999",
        status_code=418,
        details={"k": "v"},
    )
    assert e.message == "custom"
    assert e.error_code == "X-999"
    assert e.status_code == 418
    assert e.details == {"k": "v"}


def test_not_found() -> None:
    e = NotFoundError("文档不存在")
    assert e.status_code == 404
    assert e.error_code == "APP-001"
    assert "文档不存在" in str(e)


def test_permission_denied() -> None:
    e = PermissionDeniedError()
    assert e.status_code == 403
    assert e.error_code == "APP-002"


def test_tool_execution() -> None:
    e = ToolExecutionError("calc failed")
    assert e.status_code == 500
    assert e.error_code == "TOOL-001"


def test_rate_limit() -> None:
    e = RateLimitError()
    assert e.status_code == 429


def test_context_overflow() -> None:
    e = ContextOverflowError()
    assert e.status_code == 500
    assert e.error_code == "CTX-001"


def test_validation_error() -> None:
    e = ValidationError("bad input")
    assert e.status_code == 422


def test_external_service_error() -> None:
    e = ExternalServiceError()
    assert e.status_code == 502


def test_to_dict() -> None:
    """to_dict 应返回 code/message/details 三字段."""
    e = NotFoundError("x", details={"id": 42})
    d = e.to_dict()
    assert d == {"code": "APP-001", "message": "x", "details": {"id": 42}}


def test_app_error_is_exception() -> None:
    """AppError 应可被 except Exception 捕获."""
    with pytest.raises(AppError):
        raise NotFoundError("boom")
