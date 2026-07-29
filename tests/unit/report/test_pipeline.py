"""报告流水线单测 - 六阶段流转/审查打回重写/失败不抛出/沙盒落盘."""

from typing import Any

import pytest

from knowflow.agents.report.models import ReportStage
from knowflow.agents.report.pipeline import ReportPipeline
from knowflow.sandbox.workspace import WorkspaceManager
from tests.fakes import FakeChunkWithScore, FakeMinio, FakeRetrievalResult


class FakeReportLLM:
    """报告流水线 fake LLM: 按 system prompt 关键词返回可脚本化响应.

    writer_bodies / review_responses 按调用次数推进(重写场景模拟内容变化);
    gap_responses 供迭代调研缺口评估; claims_response 供主动事实核查陈述提取.
    """

    def __init__(
        self,
        spec_json: str | None = None,
        writer_bodies: list[str] | None = None,
        review_responses: list[str] | None = None,
        gap_responses: list[str] | None = None,
        claims_response: str | None = None,
    ) -> None:
        self._spec_json = spec_json or (
            '{"title": "报告", "chapters": [{"title": "一", "queries": ["q1"]}, '
            '{"title": "二", "queries": ["q2"]}]}'
        )
        self._writer_bodies = list(
            writer_bodies or ["这是一段足够长的章节正文内容, 证据见 [1] 与 [2], 结论清晰。"]
        )
        self._review_responses = list(review_responses or ['{"passed": true, "issues": []}'])
        self._gap_responses = list(
            gap_responses or ['{"sufficient": true, "gap": "足够", "follow_up_queries": []}']
        )
        self._claims_response = claims_response or '{"claims": []}'
        self.writer_calls = 0
        self.review_calls = 0
        self.gap_calls = 0

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        system = next(m["content"] for m in messages if m["role"] == "system")
        if "规划师" in system:
            return self._spec_json
        if "撰写专家" in system:
            body = self._writer_bodies[min(self.writer_calls, len(self._writer_bodies) - 1)]
            self.writer_calls += 1
            return body
        if "审查员" in system:
            resp = self._review_responses[min(self.review_calls, len(self._review_responses) - 1)]
            self.review_calls += 1
            return resp
        if "缺口评估员" in system:
            resp = self._gap_responses[min(self.gap_calls, len(self._gap_responses) - 1)]
            self.gap_calls += 1
            return resp
        if "陈述提取员" in system:
            return self._claims_response
        return "fallback"


class FakeRetriever:
    """固定返回证据的检索器."""

    def __init__(self, chunks: list[FakeChunkWithScore] | None = None) -> None:
        self._chunks = chunks or []

    async def retrieve(self, query: str, top_k: int | None = None) -> FakeRetrievalResult:
        return FakeRetrievalResult(chunks=list(self._chunks), query=query)


def _pipeline(
    llm: FakeReportLLM | None = None,
    chunks: list[FakeChunkWithScore] | None = None,
    workspace_manager: Any | None = None,
) -> ReportPipeline:
    return ReportPipeline(
        llm=llm or FakeReportLLM(),
        retriever=FakeRetriever(chunks),
        workspace_manager=workspace_manager,
    )


def _chunks(n: int = 2) -> list[FakeChunkWithScore]:
    return [
        FakeChunkWithScore(
            chunk_id=i,
            content=f"知识库证据内容{i}",
            score=0.9,
            source="hybrid",
            doc_id=i,
            doc_title=f"文档{i}",
        )
        for i in range(1, n + 1)
    ]


@pytest.mark.asyncio
async def test_pipeline_full_flow() -> None:
    """六阶段完整流转: 规格/证据/章节/参考文献/审查结论齐全."""
    result = await _pipeline(chunks=_chunks()).run("总结制度")
    assert result.stage == ReportStage.DONE
    assert result.error is None
    assert result.spec.title == "报告"
    assert len(result.chapters) == 2
    assert len(result.evidence) == 2
    assert result.review is not None and result.review.passed is True
    assert len(result.references) == 2
    # 章节正文非空且 [n] 引用均可定位证据(引用溯源成立)
    for ch in result.chapters:
        assert len(ch.body) >= 30
        assert "[1]" in ch.body or "[2]" in ch.body


@pytest.mark.asyncio
async def test_pipeline_rewrites_failed_chapter_once() -> None:
    """审查不通过(引用越界) → 携带问题清单重写一次 → 通过."""
    llm = FakeReportLLM(
        writer_bodies=[
            "这是一段章节正文内容, 引用了 [99], 需要修正。",
            "修正后的章节正文内容, 引用了相关证据 [1], 结论得到充分支持。",
        ],
    )
    result = await _pipeline(llm=llm, chunks=_chunks(1)).run("总结制度")
    assert result.stage == ReportStage.DONE
    assert result.review is not None and result.review.passed is True
    assert llm.writer_calls == 3  # 两章节首次撰写 2 次 + 问题章节打回重写 1 次
    assert "修正后的章节正文内容, 引用了相关证据 [1], 结论得到充分支持。" in result.chapters[0].body


@pytest.mark.asyncio
async def test_pipeline_stage_failure_returns_failed() -> None:
    """调研阶段异常 → 返回 FAILED 结果(不抛出)."""
    pipeline = _pipeline()
    original = pipeline._researcher.research

    async def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("调研失败")

    pipeline._researcher.research = _boom  # type: ignore[method-assign]
    try:
        result = await pipeline.run("总结制度")
        assert result.stage == ReportStage.FAILED
        assert "调研失败" in (result.error or "")
    finally:
        pipeline._researcher.research = original  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_pipeline_persists_markdown_to_sandbox() -> None:
    """报告 Markdown 落盘沙盒(虚拟路径可读回)."""
    minio = FakeMinio()
    workspace = WorkspaceManager(minio)
    result = await _pipeline(chunks=_chunks(1), workspace_manager=workspace).run(
        "总结制度", session_id=7
    )
    assert result.markdown_path.startswith("/workspace/reports/")
    ops = workspace.for_session(7)
    content = await ops.read(result.markdown_path)
    text = content.decode("utf-8")
    assert "# 报告" in text
    assert "## 参考文献" in text
    assert "[1] 知识库文档: 文档1" in text


@pytest.mark.asyncio
async def test_pipeline_progress_callback() -> None:
    """阶段进度回调: 依次收到各阶段."""
    stages: list[str] = []
    llm = FakeReportLLM()

    async def on_progress(stage: Any, detail: str) -> None:
        stages.append(stage.value if hasattr(stage, "value") else str(stage))

    await _pipeline(llm=llm, chunks=_chunks(1)).run("总结制度", on_progress=on_progress)
    assert stages[0] == ReportStage.PLANNING.value
    assert stages[-1] == ReportStage.DONE.value
    assert ReportStage.REVIEW.value in stages


@pytest.mark.asyncio
async def test_pipeline_skips_research_when_not_needed() -> None:
    """needs_research=false(Self-RAG 不检索决策): 跳过调研, 证据为空, 仍正常产出报告."""
    llm = FakeReportLLM(
        spec_json=(
            '{"title": "报告", "needs_research": false, '
            '"chapters": [{"title": "一", "queries": []}]}'
        ),
        writer_bodies=["这是基于模型知识撰写的章节正文, 无需外部证据, 内容完整充分。"],
    )
    pipeline = _pipeline(llm=llm, chunks=_chunks(2))
    details: list[str] = []

    async def _boom(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("needs_research=false 时调研不应被调用")

    original = pipeline._researcher.research
    pipeline._researcher.research = _boom  # type: ignore[method-assign]

    async def on_progress(stage: Any, detail: str) -> None:
        del stage
        details.append(detail)

    try:
        result = await pipeline.run("总结制度", on_progress=on_progress)
    finally:
        pipeline._researcher.research = original  # type: ignore[method-assign]

    assert result.stage == ReportStage.DONE
    assert result.error is None
    assert result.spec.needs_research is False
    assert result.evidence == []
    assert result.review is not None and result.review.passed is True
    assert result.references == []
    assert any("无需外部检索" in d for d in details)


@pytest.mark.asyncio
async def test_pipeline_defaults_to_research() -> None:
    """needs_research 缺失/非法: 默认 true(检索兜底), 行为与旧版一致."""
    result = await _pipeline(chunks=_chunks(1)).run("总结制度")
    assert result.spec.needs_research is True
    assert len(result.evidence) == 1


@pytest.mark.asyncio
async def test_pipeline_iterative_research_enabled() -> None:
    """迭代调研开关: 每章走缺口评估, 判足够后停止, 全流程正常完成."""
    llm = FakeReportLLM()
    pipeline = ReportPipeline(
        llm=llm,
        retriever=FakeRetriever(_chunks(1)),
        workspace_manager=None,
        iterative_research=True,
        research_max_iterations=2,
    )

    result = await pipeline.run("总结制度")
    assert result.stage == ReportStage.DONE
    assert result.error is None
    assert len(result.chapters) == 2
    assert llm.gap_calls == 2  # 两个章节各评估一次(判足够即停)


@pytest.mark.asyncio
async def test_pipeline_fact_check_enabled_passes() -> None:
    """主动事实核查开关: 陈述提取为空时全流程通过(不阻塞)."""
    llm = FakeReportLLM()
    pipeline = ReportPipeline(
        llm=llm,
        retriever=FakeRetriever(_chunks(2)),
        workspace_manager=None,
        fact_check=True,
    )

    result = await pipeline.run("总结制度")
    assert result.stage == ReportStage.DONE
    assert result.error is None
    assert result.review is not None and result.review.passed is True


@pytest.mark.asyncio
async def test_pipeline_fact_check_contradicted_triggers_rewrite() -> None:
    """主动核查发现矛盾 → 审查不通过 → 重写一次后通过."""

    class _VerdictLLM(FakeReportLLM):
        """在 FakeReportLLM 基础上按判定轮次返回矛盾/支持, 并兼容其余角色."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.verify_calls = 0

        async def ainvoke(self, messages: list[dict[str, str]]) -> str:
            system = next(m["content"] for m in messages if m["role"] == "system")
            if "事实核查员" in system:
                resp = (
                    '{"verdict": "contradicted", "reason": "与证据不符"}'
                    if self.verify_calls == 0
                    else '{"verdict": "supported", "reason": "一致"}'
                )
                self.verify_calls += 1
                return resp
            return await super().ainvoke(messages)

    verdict_llm = _VerdictLLM(
        writer_bodies=[
            "这是第一版章节正文内容, 引用了相关证据 [1], 结论清晰, 支持度充分。",
            "这是修正后的章节正文内容, 引用了相关证据 [1], 结论清晰, 支持度充分。",
        ],
        review_responses=[
            '{"passed": true, "issues": []}',
            '{"passed": true, "issues": []}',
        ],
        claims_response='{"claims": ["某错误陈述"]}',
    )
    pipeline = ReportPipeline(
        llm=verdict_llm,
        retriever=FakeRetriever(_chunks(1)),
        workspace_manager=None,
        fact_check=True,
    )

    result = await pipeline.run("总结制度")
    assert result.stage == ReportStage.DONE
    assert result.review is not None and result.review.passed is True
    # 两章各核查两轮: 首轮 1 次矛盾 + 1 次支持, 重写后全部支持
    assert verdict_llm.verify_calls == 4
