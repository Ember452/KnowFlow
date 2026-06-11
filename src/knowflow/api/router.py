"""根路由聚合 - 挂载 /api/v1 与健康检查."""

from fastapi import APIRouter

from knowflow.api.v1.router import router as v1_router

router = APIRouter()
router.include_router(v1_router)
