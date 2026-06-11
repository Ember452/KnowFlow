"""中间件单测 - 请求 ID 注入 / 限流 / 降级."""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from knowflow.api.middleware import RateLimitMiddleware, RequestContextMiddleware
from knowflow.core.exceptions import AppError
from knowflow.schemas.common import ErrorResponse


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    @app.exception_handler(AppError)
    async def _handler(_req, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=exc.error_code, message=exc.message, details=exc.details
            ).model_dump(),
        )

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "1"}

    return app


def test_request_id_generated_and_returned() -> None:
    """无 X-Request-Id 时生成, 响应头回写."""
    app = _make_app()
    client = TestClient(app)
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id") is not None


def test_request_id_passthrough() -> None:
    """携带 X-Request-Id 时透传."""
    app = _make_app()
    client = TestClient(app)
    resp = client.get("/ping", headers={"X-Request-Id": "abc-123"})
    assert resp.headers["X-Request-Id"] == "abc-123"


def test_healthz_bypasses_rate_limit() -> None:
    """/healthz 路径不限流."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/healthz")
    async def h() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)
    for _ in range(100):
        resp = client.get("/healthz")
        assert resp.status_code == 200


def test_rate_limit_blocks_after_threshold() -> None:
    """超过每分钟上限返回 429."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.exception_handler(AppError)
    async def _handler(_req, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"code": exc.error_code})

    @app.get("/q")
    async def q() -> dict[str, str]:
        return {"ok": "1"}

    # mock redis: 每次 incr 返回递增值
    fake_redis = AsyncMock()
    counter = {"n": 0}

    async def incr(_key: str) -> int:
        counter["n"] += 1
        return counter["n"]

    async def expire(_key: str, _ttl: int) -> bool:
        return True

    fake_redis.incr = incr
    fake_redis.expire = expire

    with (
        patch("knowflow.db.redis.get_redis", return_value=fake_redis),
        patch("knowflow.api.middleware.get_settings") as gs,
    ):
        gs.return_value.rate_limit_per_minute = 3
        client = TestClient(app)
        results = [client.get("/q").status_code for _ in range(5)]

    # 前 3 个 200, 之后 429
    assert results[:3] == [200, 200, 200]
    assert results[3:] == [429, 429]


def test_rate_limit_degraded_when_redis_down() -> None:
    """Redis 不可用时降级放行(不返回 429)."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/q")
    async def q() -> dict[str, str]:
        return {"ok": "1"}

    with patch("knowflow.db.redis.get_redis", side_effect=RuntimeError("no redis")):
        client = TestClient(app)
        resp = client.get("/q")
    assert resp.status_code == 200
