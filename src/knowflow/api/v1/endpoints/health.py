"""健康检查端点 - /healthz 存活 + /readyz 就绪(探测依赖连通性)."""

from fastapi import APIRouter
from sqlalchemy import text

from knowflow.schemas.common import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=ApiResponse[dict])
async def healthz() -> ApiResponse[dict]:
    """存活探针: 进程存活即 ok, 不依赖外部服务."""
    return ApiResponse(data={"status": "ok"})


@router.get("/readyz", response_model=ApiResponse[dict])
async def readyz() -> ApiResponse[dict]:
    """就绪探针: 探测 PG/Redis/Milvus/MinIO 连通性, 任一不可用标记 degraded."""
    deps: dict[str, str] = {}

    # PostgreSQL
    try:
        from knowflow.db.base import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        deps["postgres"] = "ok"
    except Exception as exc:
        deps["postgres"] = f"fail: {exc.__class__.__name__}"

    # Redis
    try:
        from knowflow.db.redis import get_redis

        await get_redis().ping()
        deps["redis"] = "ok"
    except Exception as exc:
        deps["redis"] = f"fail: {exc.__class__.__name__}"

    # Milvus
    try:
        from knowflow.db.milvus import get_milvus

        get_milvus()
        deps["milvus"] = "ok"
    except Exception as exc:
        deps["milvus"] = f"fail: {exc.__class__.__name__}"

    # MinIO
    try:
        from knowflow.db.minio import get_minio

        get_minio()
        deps["minio"] = "ok"
    except Exception as exc:
        deps["minio"] = f"fail: {exc.__class__.__name__}"

    all_ok = all(v == "ok" for v in deps.values())
    return ApiResponse(
        code="ok" if all_ok else "degraded",
        message="ok" if all_ok else "部分依赖不可用",
        data={"status": "ok" if all_ok else "degraded", "deps": deps},
    )
