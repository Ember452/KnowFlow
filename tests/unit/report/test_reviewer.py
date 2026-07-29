"""事实核查器单测 - 引用提取/规则校验/LLM 支持度校验/主动事实核查/容错."""

import pytest

from knowflow.agents.report.models import Chapter, Evidence, EvidencePack, EvidenceSource
from knowflow.agents.report.reviewer import (
    ActiveFactChecker,
    Reviewer,
    ReviewRuleChecker,
    extract_citations,
)
from tests.fakes import FakeChunkWithScore, FakeRetrievalResult


class _FakeLLM:
    def __init__(self, response: str = '{"passed": true, "issues": []}') -> None:
        self._response = response
        self.invoke_calls = 0

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        self.invoke_calls += 1
        return self._response


def _pack(evidence: list[Evidence] | None = None) -> EvidencePack:
    evs = evidence or [Evidence(source=EvidenceSource.KNOWLEDGE, content="证据1")]
    return EvidencePack(evidence=evs, chapter_index={"章节": [1]})


def _chapter(body: str, title: str = "章节") -> Chapter:
    return Chapter(title=title, body=body)


_LONG_BODY = "这是一段足够长的章节正文内容, 引用了相关证据 [1], 结论得到支持。"


def test_extract_citations() -> None:
    """提取正文 [n] 引用下标(去重保序)."""
    assert extract_citations("见 [1] 与 [2], 以及 [1] 的补充") == [1, 2, 1]
    assert extract_citations("无引用") == []


def test_rule_check_out_of_range_citation() -> None:
    """引用越界被检出(防幻觉核心规则)."""
    issues = ReviewRuleChecker().check([_chapter("结论见 [9]。")], evidence_count=2)
    assert any("越界" in i for i in issues)


def test_rule_check_short_body() -> None:
    """过短章节被检出."""
    issues = ReviewRuleChecker().check([_chapter("短")], evidence_count=2)
    assert any("过短" in i for i in issues)


def test_rule_check_pass() -> None:
    """合法引用 + 足够长度通过规则校验."""
    issues = ReviewRuleChecker().check([_chapter(_LONG_BODY)], evidence_count=2)
    assert issues == []


@pytest.mark.asyncio
async def test_review_rule_failure_short_circuits_llm() -> None:
    """规则不通过时不调用 LLM(确定性打回)."""
    llm = _FakeLLM()
    review = await Reviewer(llm=llm).review([_chapter("结论见 [9]。")], _pack())
    assert review.passed is False
    assert llm.invoke_calls == 0


@pytest.mark.asyncio
async def test_review_llm_pass() -> None:
    """规则通过 + LLM 判定通过 → 整体通过."""
    llm = _FakeLLM('{"passed": true, "issues": []}')
    review = await Reviewer(llm=llm).review([_chapter(_LONG_BODY)], _pack())
    assert review.passed is True
    assert llm.invoke_calls == 1


@pytest.mark.asyncio
async def test_review_llm_issues_rejected() -> None:
    """LLM 判定结论无证据支撑 → 不通过, 携带问题清单."""
    llm = _FakeLLM('{"passed": false, "issues": ["结论缺乏证据支撑"]}')
    review = await Reviewer(llm=llm).review([_chapter(_LONG_BODY)], _pack())
    assert review.passed is False
    assert any("结论缺乏证据支撑" in i for i in review.issues)


@pytest.mark.asyncio
async def test_review_llm_invalid_json_defaults_pass() -> None:
    """LLM 输出非法 JSON 时默认通过(容错, 不阻塞流水线)."""
    llm = _FakeLLM("不是 JSON")
    review = await Reviewer(llm=llm).review([_chapter(_LONG_BODY)], _pack())
    assert review.passed is True


@pytest.mark.asyncio
async def test_review_llm_error_defaults_pass() -> None:
    """LLM 调用异常时默认通过(容错)."""

    class _BoomLLM:
        async def ainvoke(self, messages: list[dict[str, str]]) -> str:
            raise RuntimeError("llm down")

    review = await Reviewer(llm=_BoomLLM()).review([_chapter(_LONG_BODY)], _pack())
    assert review.passed is True


# ── 主动事实核查 ──


class _ScriptedFactLLM:
    """按调用顺序返回响应的脚本 LLM(支持度检查/陈述提取/判定)."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp


class _FactRetriever:
    """记录查询的检索器(主动核查交叉验证用)."""

    def __init__(self, content: str = "年假规定为 5 天") -> None:
        self._content = content
        self.queries: list[str] = []

    async def retrieve(self, query: str, top_k: int | None = None) -> FakeRetrievalResult:
        self.queries.append(query)
        return FakeRetrievalResult(
            chunks=[
                FakeChunkWithScore(chunk_id=1, content=self._content, score=0.9, source="hybrid")
            ],
            query=query,
        )


@pytest.mark.asyncio
async def test_fact_check_contradicted_rejects() -> None:
    """陈述与检索证据矛盾 → 打回并携带问题清单."""
    llm = _ScriptedFactLLM(
        [
            '{"passed": true, "issues": []}',
            '{"claims": ["年假 15 天"]}',
            '{"verdict": "contradicted", "reason": "规定为 5 天"}',
        ]
    )
    retriever = _FactRetriever()
    review = await Reviewer(llm=llm, retriever=retriever).review([_chapter(_LONG_BODY)], _pack())
    assert review.passed is False
    assert any("矛盾" in i for i in review.issues)
    assert llm.calls == 3  # 支持度 1 + 提取 1 + 判定 1
    assert retriever.queries == ["年假 15 天"]  # 陈述直接作为验证查询


@pytest.mark.asyncio
async def test_fact_check_supported_pass() -> None:
    """陈述被检索证据支持 → 通过."""
    llm = _ScriptedFactLLM(
        [
            '{"passed": true, "issues": []}',
            '{"claims": ["年假 5 天"]}',
            '{"verdict": "supported", "reason": "一致"}',
        ]
    )
    review = await Reviewer(llm=llm, retriever=_FactRetriever()).review(
        [_chapter(_LONG_BODY)], _pack()
    )
    assert review.passed is True


@pytest.mark.asyncio
async def test_fact_check_unverified_does_not_reject() -> None:
    """证据不足(unverified) → 不打回(降级告警, 不阻塞)."""
    llm = _ScriptedFactLLM(
        [
            '{"passed": true, "issues": []}',
            '{"claims": ["某事实"]}',
            '{"verdict": "unverified", "reason": "证据不足"}',
        ]
    )
    review = await Reviewer(llm=llm, retriever=_FactRetriever()).review(
        [_chapter(_LONG_BODY)], _pack()
    )
    assert review.passed is True


@pytest.mark.asyncio
async def test_fact_check_without_retriever_skipped() -> None:
    """未注入检索源 → 跳过主动核查(只做规则 + 支持度)."""
    llm = _ScriptedFactLLM(['{"passed": true, "issues": []}'])
    review = await Reviewer(llm=llm).review([_chapter(_LONG_BODY)], _pack())
    assert review.passed is True
    assert llm.calls == 1  # 无陈述提取/判定调用


@pytest.mark.asyncio
async def test_fact_check_llm_failure_degrades() -> None:
    """提取/判定 LLM 异常 → 降级跳过, 不阻塞审查."""

    class _BoomLLM:
        async def ainvoke(self, messages: list[dict[str, str]]) -> str:
            raise RuntimeError("down")

    review = await Reviewer(llm=_BoomLLM(), retriever=_FactRetriever()).review(
        [_chapter(_LONG_BODY)], _pack()
    )
    assert review.passed is True


@pytest.mark.asyncio
async def test_fact_check_claims_capped_per_chapter() -> None:
    """提取的陈述超过预算时只核查前 max_claims_per_chapter 条."""
    llm = _ScriptedFactLLM(
        [
            '{"passed": true, "issues": []}',
            '{"claims": ["c1", "c2", "c3", "c4", "c5"]}',
            '{"verdict": "supported", "reason": "r"}',
            '{"verdict": "supported", "reason": "r"}',
            '{"verdict": "supported", "reason": "r"}',
        ]
    )
    review = await Reviewer(llm=llm, retriever=_FactRetriever(), max_claims_per_chapter=3).review(
        [_chapter(_LONG_BODY)], _pack()
    )
    assert llm.calls == 1 + 1 + 3  # 支持度 1 + 提取 1 + 判定 3
    assert review.passed is True


@pytest.mark.asyncio
async def test_fact_check_support_issue_skips_active_check() -> None:
    """支持度校验不通过 → 直接打回, 不进入主动核查(省成本)."""
    llm = _ScriptedFactLLM(['{"passed": false, "issues": ["结论无支撑"]}'])
    review = await Reviewer(llm=llm, retriever=_FactRetriever()).review(
        [_chapter(_LONG_BODY)], _pack()
    )
    assert review.passed is False
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_active_fact_checker_extract_failure_returns_empty() -> None:
    """ActiveFactChecker 单独使用: 提取失败返回空问题清单(不抛出)."""
    checker = ActiveFactChecker(llm=_ScriptedFactLLM(["不是 JSON"]), retriever=_FactRetriever())
    assert await checker.check([_chapter(_LONG_BODY)]) == []
