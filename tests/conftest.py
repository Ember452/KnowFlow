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
from tests.fakes import (
    FakeBroker,
    FakeChatLLM,
    FakeEmbeddingClient,
    FakeMinio,
    FakeRedisList,
    FakeRetriever,
)


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
    # Redis List 桩: 单实例共享, 保证 chat(短期记忆写入) 与 memory(沉淀读取) 请求间一致
    redis_list = FakeRedisList()

    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[deps.get_redis_dep] = lambda: redis_list
    app.dependency_overrides[deps.get_minio_dep] = lambda: minio
    app.dependency_overrides[deps.get_broker_dep] = lambda: broker
    app.dependency_overrides[deps.get_llm_dep] = lambda: FakeChatLLM()  # 对话端点用 fake LLM
    # Embedding 用固定向量 fake, 避免加载真实模型
    app.dependency_overrides[deps.get_embedding_dep] = lambda: FakeEmbeddingClient()
    # retriever 走模块单例, 测试可 set_retriever 替换
    deps.set_retriever(FakeRetriever())
    app.dependency_overrides[deps.get_retriever] = lambda: deps.get_retriever()
    # Skill 管理器: 每个 client 一个全新实例, 避免 toggle 状态跨用例泄漏
    from knowflow.tools.skill_manager import SkillManager

    deps.set_skill_manager(SkillManager())
    app.dependency_overrides[deps.get_skill_manager] = lambda: deps.get_skill_manager()
    # 工具注册表: 用 fake 检索器 + fake minio 构造, 避免依赖真实容器
    from knowflow.sandbox.workspace import WorkspaceManager
    from knowflow.tools.builtin import build_default_registry

    deps.set_tool_registry(
        build_default_registry(retriever=FakeRetriever(), workspace_manager=WorkspaceManager(minio))
    )
    app.dependency_overrides[deps.get_tool_registry] = lambda: deps.get_tool_registry()
    # 工具编排器: 默认关闭(避免构造真实 ChatOpenAI), 工具链路用例自行注入 fake
    app.dependency_overrides[deps.get_tool_orchestrator] = lambda: None
    # 上下文管理器: 默认关闭(避免构造真实 LLM/MinIO), 上下文策略用例自行注入 fake
    app.dependency_overrides[deps.get_context_manager] = lambda: None

    yield TestClient(app)

    deps.dispose_retriever()
    deps.dispose_tools()


@pytest.fixture
def anyio_backend() -> str:
    """pytest-asyncio 默认后端."""
    return "asyncio"
