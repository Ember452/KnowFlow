"""调研员单测 - 三源检索聚合/单源失败降级/无源跳过."""

from dataclasses import dataclass

import pytest

from knowflow.agents.report.models import ChapterPlan, EvidenceSource, ReportSpec
from knowflow.agents.report.researcher import Researcher
from tests.fakes import FakeChunkWithScore, FakeRetrievalResult


@dataclass(frozen=True)
class _FakeMemoryHit:
    content: str
    importance: float = 5.0
    score: float = 0.8


class _FakeRecaller:
    """记录调用的记忆召回器."""

    def __init__(self, hits: list[_FakeMemoryHit] | None = None, raise_error: bool = False) -> None:
        self._hits = hits or []
        self._raise_error = raise_error
        self.calls: list[tuple[str, str]] = []

    async def recall(
        self, query: str, user_id: str, top_k: int | None = None
    ) -> list[_FakeMemoryHit]:
        self.calls.append((query, user_id))
        if self._raise_error:
            raise RuntimeError("memory down")
        return list(self._hits)


class _FakeSearch:
    """callable 形态联网搜索器."""

    def __init__(
        self, results: list[dict[str, str]] | None = None, raise_error: bool = False
    ) -> None:
        self._results = results or []
        self._raise_error = raise_error
        self.calls: list[str] = []

    async def __call__(self, query: str, max_results: int = 3) -> list[dict[str, str]]:
        self.calls.append(query)
        if self._raise_error:
            raise RuntimeError("web down")
        return list(self._results)


def _spec(queries: list[str] | None = None) -> ReportSpec:
    return ReportSpec(
        title="t",
        chapters=["c"],
        research_plan=[ChapterPlan(chapter="c", queries=queries or ["q1"])],
    )


class FakeRetriever:
    """固定返回的检索器(避免依赖 tests.fakes 的默认空结果)."""

    def __init__(self, chunks: list[FakeChunkWithScore] | None = None) -> None:
        self._chunks = chunks or []

    async def retrieve(self, query: str, top_k: int | None = None) -> FakeRetrievalResult:
        return FakeRetrievalResult(chunks=list(self._chunks), query=query)


class _RecordingRetriever:
    """记录查询的检索器(迭代调研断言用)."""

    def __init__(self, content: str = "证据") -> None:
        self._content = content
        self.queries: list[str] = []

    async def retrieve(self, query: str, top_k: int | None = None) -> FakeRetrievalResult:
        self.queries.append(query)
        return FakeRetrievalResult(
            chunks=[
                FakeChunkWithScore(
                    chunk_id=len(self.queries),
                    content=f"{self._content}:{query}",
                    score=0.9,
                    source="hybrid",
                )
            ],
            query=query,
        )


class _ScriptedGapLLM:
    """缺口评估脚本 LLM: 按调用次数返回响应, 记录调用次数."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp


@pytest.mark.asyncio
async def test_research_aggregates_three_sources() -> None:
    """三源齐全时聚合全部证据, source 类型正确."""
    retriever = FakeRetriever(
        [
            FakeChunkWithScore(
                chunk_id=1,
                content="知识库内容",
                score=0.9,
                source="hybrid",
                doc_id=10,
                doc_title="制度文档",
            )
        ]
    )
    recaller = _FakeRecaller([_FakeMemoryHit("用户偏好简洁")])
    search = _FakeSearch([{"title": "网页", "snippet": "联网内容", "url": "https://x.com"}])
    researcher = Researcher(retriever=retriever, recaller=recaller, search=search)

    chapter_evidence = await researcher.research(_spec(["q1", "q2"]))
    evs = chapter_evidence["c"]
    assert len(evs) == 6  # 2 个查询、3 源各 1 条(共 6 条)
    sources = {e.source for e in evs}
    assert sources == {EvidenceSource.KNOWLEDGE, EvidenceSource.MEMORY, EvidenceSource.WEB}
    kb = next(e for e in evs if e.source == EvidenceSource.KNOWLEDGE)
    assert kb.doc_id == 10
    assert kb.title == "制度文档"
    web = next(e for e in evs if e.source == EvidenceSource.WEB)
    assert web.url == "https://x.com"
    assert len(recaller.calls) == 2  # 每个查询都走记忆召回


@pytest.mark.asyncio
async def test_research_single_source_failure_degrades() -> None:
    """联网源失败不阻塞知识库与记忆证据."""
    retriever = FakeRetriever(
        [FakeChunkWithScore(chunk_id=1, content="知识库内容", score=0.9, source="hybrid")]
    )
    recaller = _FakeRecaller([_FakeMemoryHit("记忆内容")])
    search = _FakeSearch(raise_error=True)
    researcher = Researcher(retriever=retriever, recaller=recaller, search=search)

    chapter_evidence = await researcher.research(_spec(["q1"]))
    evs = chapter_evidence["c"]
    assert len(evs) == 2
    assert {e.source for e in evs} == {EvidenceSource.KNOWLEDGE, EvidenceSource.MEMORY}


@pytest.mark.asyncio
async def test_research_no_sources_returns_empty() -> None:
    """无 retriever/recaller/search 时返回空证据(不抛错)."""
    researcher = Researcher()
    chapter_evidence = await researcher.research(_spec(["q1"]))
    assert chapter_evidence["c"] == []


@pytest.mark.asyncio
async def test_research_chapter_failure_degrades_to_empty() -> None:
    """单章节调研异常降级为空证据, 不影响其他章节."""

    class _BoomResearcher(Researcher):
        async def research_chapter(self, plan: ChapterPlan, user_id: str = "anonymous") -> list:
            if plan.chapter == "bad":
                raise RuntimeError("boom")
            return []

    researcher = _BoomResearcher()
    spec = ReportSpec(
        title="t",
        chapters=["bad", "good"],
        research_plan=[ChapterPlan("bad", ["q"]), ChapterPlan("good", ["q"])],
    )
    chapter_evidence = await researcher.research(spec)
    assert chapter_evidence["bad"] == []
    assert chapter_evidence["good"] == []


# ── 迭代调研 ──


@pytest.mark.asyncio
async def test_research_iterative_appends_follow_up_queries() -> None:
    """缺口评估判不足时追加查询并检索, 判足够后停止."""
    llm = _ScriptedGapLLM(
        [
            '{"sufficient": false, "gap": "缺竞品对比", "follow_up_queries": ["竞品B对比"]}',
            '{"sufficient": true, "gap": "足够", "follow_up_queries": []}',
        ]
    )
    retriever = _RecordingRetriever()
    researcher = Researcher(retriever=retriever)

    chapter_evidence = await researcher.research(
        _spec(["初始查询"]), iterative=True, llm=llm, max_iterations=2
    )
    assert retriever.queries == ["初始查询", "竞品B对比"]
    assert len(chapter_evidence["c"]) == 2
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_research_iterative_stops_when_sufficient() -> None:
    """首轮评估判足够 → 不追加查询, 只执行初始查询."""
    llm = _ScriptedGapLLM(['{"sufficient": true, "gap": "足够", "follow_up_queries": []}'])
    retriever = _RecordingRetriever()
    researcher = Researcher(retriever=retriever)

    chapter_evidence = await researcher.research(_spec(["q1"]), iterative=True, llm=llm)
    assert retriever.queries == ["q1"]
    assert llm.calls == 1
    assert len(chapter_evidence["c"]) == 1


@pytest.mark.asyncio
async def test_research_iterative_llm_failure_degrades() -> None:
    """LLM 缺口评估异常 → 停止迭代, 返回已有证据(不抛出)."""

    class _BoomLLM:
        async def ainvoke(self, messages: list[dict[str, str]]) -> str:
            raise RuntimeError("llm down")

    retriever = _RecordingRetriever()
    researcher = Researcher(retriever=retriever)

    chapter_evidence = await researcher.research(_spec(["q1"]), iterative=True, llm=_BoomLLM())
    assert retriever.queries == ["q1"]
    assert len(chapter_evidence["c"]) == 1


@pytest.mark.asyncio
async def test_research_iterative_respects_max_iterations() -> None:
    """LLM 一直判不足时, 最多执行 max_iterations 轮后停止(预算控制)."""
    llm = _ScriptedGapLLM(
        [
            '{"sufficient": false, "gap": "g", "follow_up_queries": ["q2"]}',
            '{"sufficient": false, "gap": "g", "follow_up_queries": ["q3"]}',
            '{"sufficient": false, "gap": "g", "follow_up_queries": ["q4"]}',
        ]
    )
    retriever = _RecordingRetriever()
    researcher = Researcher(retriever=retriever)

    await researcher.research(_spec(["q1"]), iterative=True, llm=llm, max_iterations=2)
    assert retriever.queries == ["q1", "q2"]  # 第 3 轮查询因轮次上限不执行
    assert llm.calls == 2  # 每轮检索后都评估, 轮次由 while 条件限制


@pytest.mark.asyncio
async def test_research_iterative_dedupes_executed_queries() -> None:
    """追加查询与已执行查询重复时跳过, 不重复检索."""
    llm = _ScriptedGapLLM(
        [
            '{"sufficient": false, "gap": "g", "follow_up_queries": ["q1", "q2"]}',
            '{"sufficient": true, "gap": "ok", "follow_up_queries": []}',
        ]
    )
    retriever = _RecordingRetriever()
    researcher = Researcher(retriever=retriever)

    await researcher.research(_spec(["q1"]), iterative=True, llm=llm, max_iterations=2)
    assert retriever.queries == ["q1", "q2"]


@pytest.mark.asyncio
async def test_research_default_single_round_ignores_llm() -> None:
    """默认(iterative=False)保持单轮: 只执行初始查询, 不调缺口评估 LLM."""
    llm = _ScriptedGapLLM(['{"sufficient": false, "gap": "g", "follow_up_queries": ["q2"]}'])
    retriever = _RecordingRetriever()
    researcher = Researcher(retriever=retriever)

    await researcher.research(_spec(["q1"]), llm=llm)
    assert retriever.queries == ["q1"]
    assert llm.calls == 0
