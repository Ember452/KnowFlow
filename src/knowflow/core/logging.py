"""结构化日志 - 基于 structlog, 支持 request_id 上下文绑定与 JSON/控制台双输出."""

import contextvars
import logging
import sys
from typing import Any

import structlog

from knowflow.core.config import get_settings

# 请求级上下文: 每个请求绑定唯一 request_id, 贯穿日志链路
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def _add_request_id(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor: 注入当前请求 ID."""
    rid = request_id_var.get()
    if rid is not None:
        event_dict["request_id"] = rid
    return event_dict


def setup_logging() -> None:
    """初始化 structlog 与标准 logging.

    生产环境输出 JSON; 开发/测试环境输出彩色控制台.
    """
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # 标准库 logging 兜底(structlog 会接管格式化)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_prod:
        renderers: list[Any] = [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        renderers = [structlog.dev.ConsoleRenderer(colors=settings.is_test is False)]

    structlog.configure(
        processors=[*shared_processors, *renderers],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def bind_request_id(request_id: str) -> None:
    """绑定当前请求的 request_id 到上下文."""
    request_id_var.set(request_id)


def clear_request_id() -> None:
    """清除 request_id(请求结束时调用)."""
    request_id_var.set(None)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化 logger."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
