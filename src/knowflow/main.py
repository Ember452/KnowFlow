"""FastAPI 应用工厂. 挂载 /api/v1 路由 + 中间件 + 统一异常处理."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from knowflow.api.middleware import RateLimitMiddleware, RequestContextMiddleware
from knowflow.api.router import router as api_router
from knowflow.core.config import get_settings
from knowflow.core.exceptions import AppError
from knowflow.core.lifecycle import lifespan
from knowflow.core.logging import get_logger, setup_logging
from knowflow.schemas.common import ErrorResponse


def create_app() -> FastAPI:
    """构造 FastAPI 应用. 路由/中间件/异常处理在此装配."""
    settings = get_settings()
    setup_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="企业知识库 Agent 平台 - 混合检索 + 工具治理 + Multi-Agent 编排",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── 中间件(顺序: 后添加先执行) ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)

    # ── 路由 ──
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """存活探针(根路径, 兼容旧客户端)."""
        return {"status": "ok"}

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        """根路由: 应用名与版本."""
        return {"app": settings.app_name, "version": "0.1.0"}

    # ── 统一异常处理: AppError → ErrorResponse ──
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        body = ErrorResponse(
            code=exc.error_code, message=exc.message, details=exc.details
        ).model_dump()
        return JSONResponse(status_code=exc.status_code, content=body)

    logger = get_logger("app")
    logger.info("app.created", env=settings.env, prefix=settings.api_prefix)
    return app


app = create_app()
