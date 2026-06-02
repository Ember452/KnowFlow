"""MinIO 客户端封装. 启动时自动创建业务 bucket."""

from minio import Minio

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_minio: Minio | None = None


def init_minio() -> Minio:
    """建立 MinIO 连接并确保业务 bucket 存在."""
    global _minio
    settings = get_settings()
    _minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    if not _minio.bucket_exists(settings.minio_bucket):
        _minio.make_bucket(settings.minio_bucket)
        logger.info("db.minio_bucket_created", bucket=settings.minio_bucket)
    logger.info("db.minio_initialized", endpoint=settings.minio_endpoint)
    return _minio


def dispose_minio() -> None:
    """释放 MinIO 客户端(当前为无状态, 仅清空引用)."""
    global _minio
    _minio = None
    logger.info("db.minio_disposed")


def get_minio() -> Minio:
    """获取 MinIO 客户端(已初始化时)."""
    if _minio is None:
        raise RuntimeError("MinIO not initialized; call init_minio() first")
    return _minio
