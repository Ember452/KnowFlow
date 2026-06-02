"""FastAPI 应用工厂. P1 仅暴露 /health, P4 起逐步挂载 /api/v1 路由."""

from fastapi import FastAPI

from knowflow.core.config import get_settings
from knowflow.core.lifecycle import lifespan
from knowflow.core.logging import get_logger, setup_logging


def create_app() -> FastAPI:
    """构造 FastAPI 应用实例."""
    settings = get_settings()
    setup_logging()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="企业知识库 Agent 平台 - GraphRAG + 工具治理 + Multi-Agent 编排",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        """存活探针: 进程存活即返回 ok."""
        return {"status": "ok"}

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"app": settings.app_name, "version": "0.1.0"}

    logger = get_logger("app")
    logger.info("app.created", env=settings.env)
    return app


app = create_app()
