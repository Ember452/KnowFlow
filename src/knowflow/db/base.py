"""SQLAlchemy 异步引擎与会话工厂. 提供 FastAPI 依赖注入入口 get_db()."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine() -> None:
    """创建全局 async engine 与 session factory."""
    global _engine, _session_factory
    settings = get_settings()
    _engine = create_async_engine(
        settings.postgres_dsn,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=settings.debug and settings.is_test is False,
    )
    _session_factory = async_sessionmaker(
        _engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    logger.info("db.engine_initialized", dsn=settings.postgres_dsn)


async def dispose_engine() -> None:
    """释放引擎连接池."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        logger.info("db.engine_disposed")
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取 session factory(已初始化时)."""
    if _session_factory is None:
        raise RuntimeError("DB engine not initialized; call init_engine() first")
    return _session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖: 提供事务级 AsyncSession, 请求结束自动关闭."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
