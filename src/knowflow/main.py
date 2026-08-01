"""FastAPI 应用工厂. 挂载 /api/v1 路由 + 中间件 + 统一异常处理.

前端构建产物(web/dist)存在时挂载静态托管: 单端口一条命令起全栈(见 docs/adr/0010),
目录不存在时行为与纯后端一致, 不影响无前端场景.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from knowflow.api.middleware import RateLimitMiddleware, RequestContextMiddleware
from knowflow.api.router import router as api_router
from knowflow.core.config import get_settings
from knowflow.core.exceptions import AppError
from knowflow.core.lifecycle import lifespan
from knowflow.core.logging import get_logger, setup_logging
from knowflow.schemas.common import ErrorResponse

# 前端构建产物目录(web/dist); 存在时才挂载静态托管
_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


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
    # 固定窗口限流中间件
    app.add_middleware(RateLimitMiddleware)
    # 请求上下文中间件
    app.add_middleware(RequestContextMiddleware)

    # ── 路由 ──
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """存活探针(根路径, 兼容旧客户端)."""
        return {"status": "ok"}

    @app.get("/", tags=["root"], response_model=None)
    async def root() -> FileResponse | dict[str, str]:
        """根路由: 前端构建产物存在时返回 SPA 入口页, 否则返回应用名与版本."""
        index = _WEB_DIST / "index.html"
        if index.is_file():
            return FileResponse(index)
        return {"app": settings.app_name, "version": "0.1.0"}

    # ── 前端静态托管(web/dist 存在时): 未匹配路径回退 SPA 入口 ──
    if (_WEB_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_WEB_DIST / "assets"), name="web-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
            """SPA 回退: 静态文件直接返回, 其余路径返回 index.html(前端路由处理)."""
            candidate = _WEB_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(_WEB_DIST / "index.html")

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
