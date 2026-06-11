"""pytest 公共 fixtures.

提供 SQLite+aiosqlite 内存库的 AsyncSession, 用于 repo 单测不依赖真实 PG.
PG 特有类型(JSONB)通过 JSONBType 自动降级为 JSON, LargeBinary 在 SQLite 同样支持.
SQLite 默认关闭外键级联, 通过 DBAPI connect 事件开启 PRAGMA foreign_keys=ON.

另提供 API 测试用的 TestClient(覆盖 get_db/redis/minio/broker/retriever 依赖).
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from knowflow.models import Base
from tests.fakes import FakeBroker, FakeMinio, FakeRetriever


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


@pytest_asyncio.fixture
async def api_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """API 端点测试用的 SQLite session factory(已建表, 已开外键)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.fixture
def client(
    api_session_factory: async_sessionmaker[AsyncSession],
) -> TestClient:
    """带依赖覆盖的 TestClient: get_db 用 SQLite, redis/minio/broker/retriever 用 fake.

    不触发 lifespan(无 context manager), 避免连接真实外部依赖.
    retriever 通过 deps.set_retriever 注入(默认空 fake), 测试可替换.
    """
    from knowflow.api import deps
    from knowflow.main import create_app

    app = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with api_session_factory() as session:
            yield session

    minio = FakeMinio()
    broker = FakeBroker()

    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[deps.get_redis_dep] = lambda: object()  # 占位, 中间件降级
    app.dependency_overrides[deps.get_minio_dep] = lambda: minio
    app.dependency_overrides[deps.get_broker_dep] = lambda: broker
    # retriever 走模块单例, 测试可 set_retriever 替换
    deps.set_retriever(FakeRetriever())
    app.dependency_overrides[deps.get_retriever] = lambda: deps.get_retriever()

    yield TestClient(app)

    deps.dispose_retriever()


@pytest.fixture
def anyio_backend() -> str:
    """pytest-asyncio 默认后端."""
    return "asyncio"
