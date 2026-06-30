"""记忆管理器单测 - 观察/沉淀(阈值筛选+压缩+清空)/召回编排."""

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import Settings
from knowflow.memory.compressor import Compressor
from knowflow.memory.importance import ImportanceScorer
from knowflow.memory.long_term import LongTermMemoryManager
from knowflow.memory.manager import MemoryManager
from knowflow.memory.short_term import ShortTermMemory
from tests.fakes import FakeChatLLM, FakeEmbeddingClient, FakeRedisList


class _JsonLLM:
    """返回固定 JSON 的 fake LLM(重要性打分解析用)."""

    def __init__(self, answer: str) -> None:
        self._answer = answer

    async def ainvoke(self, messages):  # type: ignore[no-untyped-def]
        return self._answer


class _CharEmbedding:
    """字符覆盖度向量 fake: 相同文本向量相同(相似度 1), 字符重叠越高相似度越高."""

    _DIM = 64

    def embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._DIM
        for ch in text:
            vec[ord(ch) % self._DIM] += 1.0
        return vec


def _manager(db_session: AsyncSession) -> tuple[MemoryManager, ShortTermMemory]:
    """构造 MemoryManager: 重要性用规则打分(可预测), 压缩用 fake LLM."""
    settings = Settings(memory_sediment_threshold=6.0, memory_sediment_interval=5)
    short_term = ShortTermMemory(FakeRedisList(), ttl_seconds=3600)
    manager = MemoryManager(
        short_term=short_term,
        importance=ImportanceScorer(),  # 规则打分: 偏好类 9 分, 寒暄 2 分
        compressor=Compressor(FakeChatLLM(answer="用户偏好摘要")),
        long_term=LongTermMemoryManager(db_session, embedding_client=FakeEmbeddingClient()),
        settings=settings,
    )
    return manager, short_term


def test_should_sediment_interval() -> None:
    """每 N 轮触发一次沉淀."""
    assert MemoryManager.should_sediment(0) is False
    assert MemoryManager.should_sediment(3) is False
    assert MemoryManager.should_sediment(5) is True
    assert MemoryManager.should_sediment(10, interval=5) is True
    assert MemoryManager.should_sediment(6, interval=5) is False


async def test_observe_writes_short_term(db_session: AsyncSession) -> None:
    """观察消息写入短期记忆."""
    manager, short_term = _manager(db_session)
    await manager.observe("s1", "user", "你好")
    await manager.observe("s1", "assistant", "有什么可以帮你")
    assert await short_term.count("s1") == 2


async def test_sediment_filters_important_and_persists(db_session: AsyncSession) -> None:
    """沉淀: 仅高重要性用户消息入库, 短期清空, summary 为压缩结果."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    manager, short_term = _manager(db_session)
    await manager.observe(sid, "user", "你好")  # 规则 2 分, 不沉淀
    await manager.observe(sid, "user", "请记住我喜欢用 Markdown 写文档")  # 9 分
    await manager.observe(sid, "assistant", "已记录")  # assistant 不参与

    saved = await manager.sediment(sid, "u1")
    assert saved == 1
    assert await short_term.count(sid) == 0

    memories = await manager._long_term.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].content == "请记住我喜欢用 Markdown 写文档"
    assert memories[0].summary == "用户偏好摘要"
    assert memories[0].importance == 9.0


async def test_sediment_no_important_clears_short_term(db_session: AsyncSession) -> None:
    """无高价值消息时不入库, 但短期记忆被清空(已消费)."""
    manager, short_term = _manager(db_session)
    await manager.observe("s1", "user", "你好")
    saved = await manager.sediment("s1", "u1")
    assert saved == 0
    assert await short_term.count("s1") == 0
    assert await manager._long_term.list_by_user("u1") == []


async def test_sediment_empty_short_term(db_session: AsyncSession) -> None:
    manager, _ = _manager(db_session)
    assert await manager.sediment("s1", "u1") == 0


async def test_recall_via_manager(db_session: AsyncSession) -> None:
    """管理器召回委托长期记忆(语义相似)."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    manager, _ = _manager(db_session)
    await manager._long_term.save(
        user_id="u1", session_id=sid, content="报销需要发票", importance=8.0
    )
    await db_session.commit()

    hits = await manager.recall("报销流程", "u1", top_k=2)
    assert len(hits) == 1
    assert hits[0].content == "报销需要发票"
    assert manager.recall_text(hits) == "- 报销需要发票"
    assert manager.recall_text([]) == ""


async def test_save_dedup_same_content_updates_importance(db_session: AsyncSession) -> None:
    """同一内容重复保存: 覆盖更新旧条目(不新增), importance 取较大值."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())

    mid1 = await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档", importance=8.0
    )
    mid2 = await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档", importance=9.5
    )
    assert mid1 == mid2
    memories = await manager.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].content == "请记住我喜欢用 Markdown 写文档"
    assert memories[0].importance == 9.5


async def test_save_dedup_similar_content_merged(db_session: AsyncSession) -> None:
    """近似表述(高字符重叠)视为同一偏好: 覆盖更新为最新表述."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())

    await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档", importance=8.0
    )
    await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档和笔记", importance=8.5
    )
    memories = await manager.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].content == "请记住我喜欢用 Markdown 写文档和笔记"


async def test_save_dedup_distinct_preferences_kept(db_session: AsyncSession) -> None:
    """不同主题偏好不合并, 各自独立存储."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    manager = LongTermMemoryManager(db_session, embedding_client=_CharEmbedding())

    mid1 = await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档", importance=9.0
    )
    mid2 = await manager.save(
        user_id="u1", session_id=sid, content="我的目标是成为架构师", importance=8.0
    )
    assert mid1 != mid2
    assert len(await manager.list_by_user("u1")) == 2


async def test_save_dedup_text_fallback_without_embedding(db_session: AsyncSession) -> None:
    """无 embedding 时按文本相似度兜底去重(仅差标点的重复表述合并)."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    manager = LongTermMemoryManager(db_session)  # 无 embedding_client

    await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档。", importance=8.0
    )
    await manager.save(
        user_id="u1", session_id=sid, content="请记住我喜欢用 Markdown 写文档", importance=9.0
    )
    memories = await manager.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].content == "请记住我喜欢用 Markdown 写文档"
    assert memories[0].importance == 9.0


async def test_sediment_dedup_same_preference(db_session: AsyncSession) -> None:
    """沉淀链路: 同一偏好跨轮次重复出现, 长期记忆不膨胀."""
    from knowflow.db.repositories.session_repo import SessionRepo

    sess = await SessionRepo(db_session).create(user_id="u1")
    sid = int(sess.id)
    settings = Settings(memory_sediment_threshold=6.0, memory_sediment_interval=5)
    short_term = ShortTermMemory(FakeRedisList(), ttl_seconds=3600)
    manager = MemoryManager(
        short_term=short_term,
        importance=ImportanceScorer(),  # 规则打分: 偏好类 9 分
        compressor=Compressor(FakeChatLLM(answer="用户偏好摘要")),
        long_term=LongTermMemoryManager(db_session, embedding_client=_CharEmbedding()),
        settings=settings,
    )
    await manager.observe(sid, "user", "请记住我喜欢用 Markdown 写文档")
    await manager.sediment(sid, "u1")
    await manager.observe(sid, "user", "请记住我喜欢用 Markdown 写文档")
    await manager.sediment(sid, "u1")

    memories = await manager._long_term.list_by_user("u1")
    assert len(memories) == 1
    assert memories[0].content == "请记住我喜欢用 Markdown 写文档"
