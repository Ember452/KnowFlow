"""记忆去重 pgvector 路径单测.

SQLite 无法执行真实向量 SQL, 这里覆盖可离线验证的部分:
- 路由: 非 PG(SQLite)下 SQL 路径不可用, save 不写向量列, 去重降级 Python 全量;
- 二次校验: 候选集内精确余弦校验命中阈值 / 未命中不合并;
- 编译: PG 方言下生成 <=> + CAST(vector) 的 top-N 语句与 DDL(无需真实 PG).
真实 PG + pgvector 的端到端验证见 docs/tests/指标测试-记忆去重pgvector.md.
"""

from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.schema import CreateTable

from knowflow.memory.long_term import LongTermMemoryManager
from knowflow.memory.store import LongTermStore, _build_dedup_query, _pgvector_ready
from knowflow.models.memory import LongTermMemory
from tests.fakes import FakeEmbeddingClient


class _CharEmbedding:
    """字符覆盖度向量 fake: 相同文本向量相同(相似度 1), 字符重叠越高相似度越高."""

    _DIM = 64

    def embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._DIM
        for ch in text:
            vec[ord(ch) % self._DIM] += 1.0
        return vec


async def test_pgvector_ready_false_on_sqlite(db_session: AsyncSession) -> None:
    """SQLite 不具备 pgvector 能力(不发起 SQL, 直接按方言短路)."""
    assert await _pgvector_ready(db_session) is False


async def test_candidates_unavailable_on_sqlite(db_session: AsyncSession) -> None:
    """非 PG 时 find_duplicate_candidates 返回 None(调用方降级 Python)."""
    store = LongTermStore(db_session)
    assert await store.find_duplicate_candidates("u1", [0.1, 0.2], 5) is None


async def test_save_skips_vec_on_sqlite(db_session: AsyncSession) -> None:
    """SQLite 下 save 正常写 embedding, 但向量列不写(保持空列)."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    store = LongTermStore(db_session, embedding_client=FakeEmbeddingClient())
    mid = await store.save(
        user_id="u1", session_id=int(sess.id), content="报销需要发票", importance=8.0
    )
    memory = await db_session.get(LongTermMemory, mid)
    assert memory is not None
    assert memory.embedding is not None
    assert memory.embedding_vec is None


async def test_dedup_falls_back_to_python_scan(db_session: AsyncSession, monkeypatch) -> None:
    """数据库路径不可用(返回 None)时降级 Python 全量扫描, 去重行为不变."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())

    async def _unavailable(user_id: str, vec: list[float], top_n: int) -> None:
        return None

    monkeypatch.setattr(manager._store, "find_duplicate_candidates", _unavailable)
    mid1 = await manager.save(
        user_id="u1",
        session_id=int(sess.id),
        content="请记住我喜欢用 Markdown 写文档",
        importance=8.0,
    )
    mid2 = await manager.save(
        user_id="u1",
        session_id=int(sess.id),
        content="请记住我喜欢用 Markdown 写文档",
        importance=9.5,
    )
    assert mid1 == mid2
    memories = await manager.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].importance == 9.5


async def test_dedup_verify_candidates_hit(db_session: AsyncSession, monkeypatch) -> None:
    """候选集二次校验: 精确余弦 ≥ 阈值命中, 覆盖更新旧条目."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())
    mid1 = await manager.save(
        user_id="u1",
        session_id=int(sess.id),
        content="请记住我喜欢用 Markdown 写文档",
        importance=8.0,
    )

    async def _candidates(user_id: str, vec: list[float], top_n: int):
        return await manager._store.list_by_user(user_id)

    monkeypatch.setattr(manager._store, "find_duplicate_candidates", _candidates)
    mid2 = await manager.save(
        user_id="u1",
        session_id=int(sess.id),
        content="请记住我喜欢用 Markdown 写文档和笔记",
        importance=8.5,
    )
    assert mid2 == mid1
    memories = await manager.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].content == "请记住我喜欢用 Markdown 写文档和笔记"
    assert memories[0].importance == 8.5


async def test_dedup_verify_candidates_miss(db_session: AsyncSession, monkeypatch) -> None:
    """候选集二次校验: 低于阈值(不同主题)不合并, 各自独立存储."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())
    mid1 = await manager.save(
        user_id="u1",
        session_id=int(sess.id),
        content="请记住我喜欢用 Markdown 写文档",
        importance=9.0,
    )

    async def _candidates(user_id: str, vec: list[float], top_n: int):
        return await manager._store.list_by_user(user_id)

    monkeypatch.setattr(manager._store, "find_duplicate_candidates", _candidates)
    mid2 = await manager.save(
        user_id="u1", session_id=int(sess.id), content="我的目标是成为架构师", importance=8.0
    )
    assert mid1 != mid2
    assert len(await manager.list_by_user("u1")) == 2


async def test_dedup_candidates_empty_returns_none(db_session: AsyncSession, monkeypatch) -> None:
    """用户无任何记忆时候选为空, save 直接新增(不误判重复)."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())

    async def _candidates(user_id: str, vec: list[float], top_n: int):
        return await manager._store.list_by_user(user_id)

    monkeypatch.setattr(manager._store, "find_duplicate_candidates", _candidates)
    mid = await manager.save(
        user_id="u1",
        session_id=int(sess.id),
        content="请记住我喜欢用 Markdown 写文档",
        importance=8.0,
    )
    assert mid is not None
    assert len(await manager.list_by_user("u1")) == 1


def test_build_dedup_query_compiles_for_postgresql() -> None:
    """PG 方言下编译出余弦距离 top-N 语句(<=> 算子 + CAST vector 绑定)."""
    stmt = _build_dedup_query("u1", "[0.1,0.2]", 10)
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "embedding_vec <=> CAST(%(query_vec)s AS vector)" in sql
    assert "user_id" in sql
    assert "LIMIT" in sql


def test_memory_ddl_has_vector_column() -> None:
    """PG 方言 DDL 含 embedding_vec vector(1024) 列(迁移 0004 目标结构)."""
    ddl = str(CreateTable(LongTermMemory.__table__).compile(dialect=postgresql.dialect()))
    assert "embedding_vec" in ddl
    assert "VECTOR(1024)" in ddl
