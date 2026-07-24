"""记忆治理单测 - 冲突检测/留痕 + 蒸馏摘要 + 召回可观测."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from knowflow.memory.conflict import ConflictDetector, ConflictStore
from knowflow.memory.long_term import LongTermMemoryManager
from knowflow.memory.manager import MemoryManager
from knowflow.models import Base
from knowflow.models.memory import LongTermMemory


def _memory(id_: int, content: str) -> LongTermMemory:
    return LongTermMemory(
        id=id_,
        user_id="u1",
        session_id=1,
        content=content,
        importance=7.0,
    )


# ── 冲突检测器(纯规则) ──


@pytest.mark.parametrize(
    "new_content,old_content,expect_conflict",
    [
        # 主题相似 + 否定极性反转 → 冲突
        ("用户喜欢喝咖啡", "用户不喜欢喝咖啡", True),
        ("推荐使用 A 方案", "不推荐使用 A 方案", True),
        # 主题相似 + 数值不一致 → 冲突
        ("会议预算调整为 200 元", "会议预算为 100 元", True),
        # 主题不同 → 不冲突
        ("用户喜欢咖啡", "用户负责报销审批", False),
        # 主题相似但态度一致 → 不冲突
        ("用户喜欢喝咖啡", "用户喜欢喝美式咖啡", False),
        # 数值相同 → 不冲突
        ("会议预算调整为 200 元", "会议预算为 200 元", False),
    ],
)
def test_detector_rule_cases(new_content: str, old_content: str, expect_conflict: bool) -> None:
    """启发式规则覆盖方向反转/数值矛盾, 不误伤同向/同值/异主题."""
    findings = ConflictDetector().detect(new_content, [_memory(1, old_content)])
    assert (len(findings) > 0) is expect_conflict


def test_detector_skips_empty_and_ranks_by_similarity() -> None:
    """空内容不检测; 多冲突按相似度降序(高相似真实矛盾在前)."""
    detector = ConflictDetector()
    assert detector.detect("", [_memory(1, "任意内容")]) == []
    findings = detector.detect(
        "用户不喜欢喝咖啡", [_memory(1, "用户喜欢喝茶"), _memory(2, "用户喜欢喝咖啡因饮料")]
    )
    assert len(findings) == 2
    # 相似度高的排前面(与咖啡主题更接近的矛盾在前)
    assert findings[0].old_memory_id == 2


# ── 冲突存储(落库留痕) ──


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """StaticPool 共享内存 SQLite."""
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


@pytest.mark.asyncio
async def test_conflict_store_record_and_list(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """冲突记录写入/查询/解决(留痕供审查)."""
    async with session_factory() as session:
        store = ConflictStore(session)
        finding = ConflictDetector().detect("用户不喜欢喝咖啡", [_memory(5, "用户喜欢喝咖啡")])[0]
        cid = await store.record(finding, user_id="u1", new_content="用户不喜欢喝咖啡")
        await session.commit()

        conflicts = await store.list_by_user("u1")
        assert len(conflicts) == 1
        assert conflicts[0].status == "pending"
        assert conflicts[0].old_memory_id == 5
        assert "态度反转" in conflicts[0].reason

        pending = await store.list_pending("u1")
        assert len(pending) == 1
        assert await store.resolve(cid) is True
        await session.commit()
        assert await store.list_pending("u1") == []


# ── 记忆管理器治理链路(蒸馏 + 冲突 + 可观测) ──


class FakeShortTerm:
    """fake 短期记忆: 固定消息列表."""

    def __init__(self, messages: list[dict[str, str]]) -> None:
        self._messages = messages
        self.cleared: list[Any] = []

    async def get_recent(self, session_id: Any, n: int) -> list[dict[str, str]]:
        return self._messages

    async def clear(self, session_id: Any) -> None:
        self.cleared.append(session_id)


class FakeImportance:
    """fake 重要性评分: 全部高分(触发沉淀)."""

    async def score(self, content: str) -> float:
        return 8.0


class FakeCompressor:
    """fake 压缩器: 固定摘要(蒸馏产物)."""

    async def compress(self, contents: list[str]) -> str:
        return "核心摘要: " + " / ".join(c[:10] for c in contents)


class FakeTracer:
    """fake tracer: 记录 span 调用(可观测验证)."""

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    async def start_span(
        self, span_type: str, name: str, *, input: dict | None = None, **kw: Any
    ) -> Any:
        span = {"type": span_type, "name": name, "input": input}
        self.spans.append(span)
        return span

    async def end_span(self, span: Any, output: dict | None = None, **kw: Any) -> None:
        span["output"] = output


@pytest.mark.asyncio
async def test_sediment_distills_summary_and_tracks_conflict(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """沉淀链路: 蒸馏摘要落库 + 冲突检测留痕 + 长期记忆照常写入."""
    async with session_factory() as session:
        long_term = LongTermMemoryManager(session)
        # 先写入存量记忆(制造冲突源)
        await long_term.save(user_id="u1", session_id=1, content="用户喜欢喝咖啡", importance=8.0)
        manager = MemoryManager(
            short_term=FakeShortTerm([{"role": "user", "content": "用户不喜欢喝咖啡了"}]),
            importance=FakeImportance(),
            compressor=FakeCompressor(),
            long_term=long_term,
            conflict_store=ConflictStore(session),
        )

        count = await manager.sediment(1, "u1")
        await session.commit()
        assert count == 1

        # 长期记忆已写入
        memories = await long_term.list_by_user("u1")
        assert len(memories) == 2  # 存量 + 新增

        # 冲突已留痕
        conflicts = await ConflictStore(session).list_by_user("u1")
        assert len(conflicts) == 1
        assert "态度反转" in conflicts[0].reason

        # 蒸馏摘要已沉淀, 可召回注入
        summary = await manager.latest_summary("u1")
        assert summary and "核心摘要" in summary
        assert await manager.latest_summary("no_such_user") is None


@pytest.mark.asyncio
async def test_recall_records_tracer_span(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """召回可观测: 命中明细经 tracer span 记录(id + score)."""
    async with session_factory() as session:
        long_term = LongTermMemoryManager(session)
        await long_term.save(user_id="u1", session_id=1, content="用户喜欢简洁回答", importance=8.0)
        tracer = FakeTracer()
        manager = MemoryManager(
            short_term=FakeShortTerm([]),
            importance=FakeImportance(),
            compressor=FakeCompressor(),
            long_term=long_term,
            tracer=tracer,
        )
        hits = await manager.recall("回答风格", "u1")
        assert hits  # 命中存量记忆
        assert tracer.spans, "recall 应记录 span"
        span = tracer.spans[0]
        assert span["type"] == "memory_recall"
        assert span["output"]["count"] == len(hits)
        assert all("memory_id" in h for h in span["output"]["hits"])


@pytest.mark.asyncio
async def test_recall_without_tracer_does_not_fail(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """无 tracer 时召回正常(可观测降级不阻塞)."""
    async with session_factory() as session:
        long_term = LongTermMemoryManager(session)
        await long_term.save(user_id="u1", session_id=1, content="用户喜欢简洁回答", importance=8.0)
        manager = MemoryManager(
            short_term=FakeShortTerm([]),
            importance=FakeImportance(),
            compressor=FakeCompressor(),
            long_term=long_term,
        )
        hits = await manager.recall("回答风格", "u1")
        assert hits
        assert await manager.recall("x", "") == []
