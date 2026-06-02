"""Milvus 客户端封装. collection 生命周期由 scripts/init_milvus.py 管理."""

from pymilvus import MilvusClient

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_milvus: MilvusClient | None = None


def init_milvus() -> MilvusClient:
    """建立 Milvus 连接."""
    global _milvus
    settings = get_settings()
    _milvus = MilvusClient(uri=settings.milvus_uri)
    logger.info("db.milvus_initialized", uri=settings.milvus_uri)
    return _milvus


def dispose_milvus() -> None:
    """关闭 Milvus 连接."""
    global _milvus
    if _milvus is not None:
        _milvus.close()
        logger.info("db.milvus_disposed")
    _milvus = None


def get_milvus() -> MilvusClient:
    """获取 Milvus 客户端(已初始化时)."""
    if _milvus is None:
        raise RuntimeError("Milvus not initialized; call init_milvus() first")
    return _milvus
