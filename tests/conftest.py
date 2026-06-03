"""pytest 公共 fixtures.

提供 SQLite+aiosqlite 内存库的 AsyncSession, 用于 repo 单测不依赖真实 PG.
PG 特有类型(JSONB)通过 JSONBType 自动降级为 JSON, LargeBinary 在 SQLite 同样支持.
SQLite 默认关闭外键级联, 通过 DBAPI connect 事件开启 PRAGMA foreign_keys=ON.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from knowflow.models import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """每条用例一个内存 SQLite 库: 建表 → 用例执行 → 清库.

    使用 aiosqlite 驱动, 单测无需真实 PG 容器.
    启用 PRAGMA foreign_keys=ON 以验证 ON DELETE CASCADE 行为.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # 在每个 DBAPI 连接上开启 SQLite 外键约束, 让级联删除生效
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    """pytest-asyncio 默认后端."""
    return "asyncio"
