"""HTTP 中间件 - 请求 ID / 访问日志 / 限流 / CORS.

- RequestContextMiddleware: 生成/透传 X-Request-Id, 绑定 structlog 上下文, 记录访问日志.
- RateLimitMiddleware: Redis 固定窗口限流(每 IP 每分钟), Redis 不可用时降级放行.
- CORS 在 main.py 用 FastAPI CORSMiddleware 配置.
"""

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from knowflow.core.config import get_settings
from knowflow.core.constants import DEFAULT_RATE_LIMIT_PER_MINUTE
from knowflow.core.logging import bind_request_id, clear_request_id, get_logger

logger = get_logger("middleware")

_HEADER_REQUEST_ID = "X-Request-Id"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """请求上下文中间件: 注入 request_id + 访问日志."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(_HEADER_REQUEST_ID) or uuid.uuid4().hex
        bind_request_id(request_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            clear_request_id()

        duration_ms = (time.perf_counter() - start) * 1000
        response.headers[_HEADER_REQUEST_ID] = request_id
        logger.info(
            "http.access",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """固定窗口限流: 每 IP 每分钟 rate_limit_per_minute 次. Redis 不可用时降级放行."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # 健康检查路径不限流
        if request.url.path.endswith(("/healthz", "/readyz", "/health")):
            return await call_next(request)

        settings = get_settings()
        limit = settings.rate_limit_per_minute or DEFAULT_RATE_LIMIT_PER_MINUTE
        client_ip = request.client.host if request.client else "unknown"

        try:
            from knowflow.db.redis import get_redis

            redis = get_redis()
            key = f"knowflow:ratelimit:{client_ip}:{int(time.time() // 60)}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 60)
            if count > limit:
                logger.warning("http.rate_limited", ip=client_ip, count=count, limit=limit)
                # 中间件抛出的异常不会被 FastAPI exception_handler 捕获, 直接返回 429
                return JSONResponse(
                    status_code=429,
                    content={"code": "APP-003", "message": f"请求过于频繁, 每分钟上限 {limit} 次"},
                )
        except Exception as exc:
            # Redis 不可用, 降级放行(不阻塞业务)
            logger.warning("http.ratelimit_degraded", error=str(exc))

        return await call_next(request)
