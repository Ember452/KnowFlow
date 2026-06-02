"""结构化日志单测 - request_id 上下文绑定与 logger 获取."""

from knowflow.core.logging import (
    bind_request_id,
    clear_request_id,
    get_logger,
    request_id_var,
    setup_logging,
)


def test_request_id_bind_and_clear() -> None:
    """bind 后应可读取, clear 后应恢复 None."""
    clear_request_id()
    assert request_id_var.get() is None

    bind_request_id("req-abc-123")
    assert request_id_var.get() == "req-abc-123"

    clear_request_id()
    assert request_id_var.get() is None


def test_get_logger_returns_bound_logger() -> None:
    """get_logger 应返回可调用的 BoundLogger."""
    setup_logging()
    logger = get_logger("test")
    # BoundLogger 应支持 info/debug/warning/error 等方法
    assert hasattr(logger, "info")
    assert hasattr(logger, "error")
    logger.info("smoke log from test", source="unit_test")


def test_setup_logging_idempotent() -> None:
    """多次调用 setup_logging 不应报错."""
    setup_logging()
    setup_logging()
