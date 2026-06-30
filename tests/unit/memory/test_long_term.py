"""长期记忆单测 - store 持久化/删除/召回排序(相似度+时间衰减)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.memory.long_term import LongTermMemoryManager
from knowflow.memory.recall import cosine_similarity
from knowflow.memory.store import LongTermStore, deserialize_embedding
from knowflow.models.memory import LongTermMemory
from tests.fakes import FakeEmbeddingClient


async def _session_id(db_session: AsyncSession) -> int:
    """创建会话并返回 id(满足 session_id 外键约束)."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    return int(sess.id)


def _manager(session: AsyncSession) -> LongTermMemoryManager:
    return LongTermMemoryManager(session, embedding_client=FakeEmbeddingClient())


async def test_save_persists_with_embedding(db_session: AsyncSession) -> None:
    """保存记忆: 内容/重要性/embedding 序列化落库."""
    sid = await _session_id(db_session)
    manager = _manager(db_session)
    memory_id = await manager.save(
        user_id="u1",
        session_id=sid,
        content="用户报销偏好: 电子发票",
        importance=8.0,
        summary="报销偏好",
    )
    await db_session.commit()

    memories = await manager.list_by_user("u1")
    assert len(memories) == 1
    mem = memories[0]
    assert mem.content == "用户报销偏好: 电子发票"
    assert mem.importance == 8.0
    assert mem.summary == "报销偏好"
    # embedding 已序列化且可反序列化
    vec = deserialize_embedding(mem.embedding)
    assert vec == [1.0, 0.0, 0.0]
    assert memory_id == int(mem.id)


async def test_save_without_embedding_client(db_session: AsyncSession) -> None:
    """无 embedding 客户端时记忆照常入库(embedding=None), 召回退化为重要性+新鲜度."""
    sid = await _session_id(db_session)
    manager = LongTermMemoryManager(db_session)
    await manager.save(user_id="u2", session_id=sid, content="普通记忆", importance=5.0)
    await db_session.commit()

    memories = await manager.list_by_user("u2")
    assert memories[0].embedding is None


async def test_delete_removes_memory(db_session: AsyncSession) -> None:
    sid = await _session_id(db_session)
    manager = _manager(db_session)
    memory_id = await manager.save(user_id="u1", session_id=sid, content="待删除", importance=7.0)
    await db_session.commit()
    assert await manager.delete(memory_id) is True
    await db_session.commit()
    assert await manager.list_by_user("u1") == []
    assert await manager.delete(memory_id) is False


async def test_recall_ranks_by_similarity(db_session: AsyncSession) -> None:
    """召回: 语义相似记忆排前, top_k 截断, last_recall 被 touch."""
    sid = await _session_id(db_session)
    # 用 store 直写构造数据, 绕开门面 save 的去重合并(本用例只验证召回排序)
    store = LongTermStore(db_session, embedding_client=FakeEmbeddingClient())
    for content in ("报销流程是填写单据", "年假政策是 10 天", "报销需要发票"):
        await store.save(user_id="u1", session_id=sid, content=content, importance=6.0)
    await db_session.commit()

    manager = LongTermMemoryManager(db_session, store=store, embedding_client=FakeEmbeddingClient())
    hits = await manager.recall("报销怎么做", "u1", top_k=2)
    assert [h.content for h in hits] == ["报销流程是填写单据", "报销需要发票"]
    assert all(h.score > 0 for h in hits)
    # last_recall 已更新
    await db_session.commit()
    memories = await manager.list_by_user("u1")
    recalled_ids = {h.memory_id for h in hits}
    for m in memories:
        if int(m.id) in recalled_ids:
            assert m.last_recall is not None
        else:
            assert m.last_recall is None


async def test_recall_time_decay_boosts_recent_recall(db_session: AsyncSession) -> None:
    """时间衰减: 刚召回过的记忆新鲜度高, 排序占优(同相似度下)."""
    sid = await _session_id(db_session)
    store = LongTermStore(db_session, embedding_client=None)
    # 无 embedding → 相似度恒 0, 排序由重要性+新鲜度决定
    id_a = await store.save(user_id="u1", session_id=sid, content="记忆A", importance=6.0)
    id_b = await store.save(user_id="u1", session_id=sid, content="记忆B", importance=6.0)
    await db_session.commit()

    # 手动设置 last_recall: A 刚刚召回过, B 很久前
    from sqlalchemy import update

    now = datetime.now(UTC)
    await db_session.execute(
        update(LongTermMemory)
        .where(LongTermMemory.id == id_a)
        .values(last_recall=now - timedelta(hours=1))
    )
    await db_session.execute(
        update(LongTermMemory)
        .where(LongTermMemory.id == id_b)
        .values(last_recall=now - timedelta(days=30))
    )
    await db_session.commit()

    manager = LongTermMemoryManager(db_session, store=store)
    hits = await manager.recall("查询", "u1", top_k=2)
    assert [h.memory_id for h in hits] == [id_a, id_b]


def test_cosine_similarity() -> None:
    """余弦相似度计算与边界."""
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([], [1, 0]) == 0.0
    assert cosine_similarity([1], [1, 0]) == 0.0
    assert cosine_similarity([0, 0], [0, 0]) == 0.0
