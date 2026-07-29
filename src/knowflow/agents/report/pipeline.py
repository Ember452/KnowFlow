"""报告流水线 - 六阶段编排: 规划 → 并行调研 → 融合 → 并行撰写 → 审查 → 落盘.

- 并行: 调研(章节间)与撰写(章节间)复用 agents/concurrent.py(asyncio.gather+超时+降级);
- 审查: 规则校验(引用越界/过短) + LLM 支持度校验, 不通过携带问题清单打回重写一次;
- 降级: 任一阶段失败标记 FAILED 返回结构化错误(不抛出); 落盘失败仅告警不致命;
- 进度: 阶段切换经 on_progress(stage, detail) 回调上抛(SSE progress 事件源).
"""

import re
from typing import Any
from uuid import uuid4

from knowflow.agents.concurrent import SubtaskResult, run_concurrent
from knowflow.agents.report.models import (
    Chapter,
    Evidence,
    EvidencePack,
    ReportResult,
    ReportSpec,
    ReportStage,
)
from knowflow.agents.report.planner import Planner
from knowflow.agents.report.researcher import Researcher
from knowflow.agents.report.reviewer import Reviewer
from knowflow.agents.report.synthesizer import Synthesizer
from knowflow.agents.report.writer import Writer
from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_ISSUE_CHAPTER_RE = re.compile(r"章节 '([^']+)'")


class ReportPipeline:
    """报告流水线编排器(与问答编排器并存, 决策见 ADR 0008)."""

    def __init__(
        self,
        llm: Any | None = None,
        retriever: Any | None = None,
        recaller: Any | None = None,
        search: Any | None = None,
        workspace_manager: Any | None = None,
        settings: Settings | None = None,
        *,
        iterative_research: bool = False,
        research_max_iterations: int = 2,
        research_max_follow_up_queries: int = 3,
        fact_check: bool = False,
        max_claims_per_chapter: int = 3,
    ) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake(实现 ainvoke).
            retriever: 知识库检索器(HybridRetriever 或实现 async retrieve).
            recaller: 记忆召回器(实现 async recall); None 跳过记忆源.
            search: 联网搜索器(SearchTool 或 callable); None 跳过联网源.
            workspace_manager: 沙盒管理器; None 时懒加载(失败则不落盘).
            settings: Settings 单例.
            iterative_research: 开启迭代调研(初始查询 → 缺口评估 → 追加查询,
                最多 research_max_iterations 轮); 默认关闭保持单轮行为.
            research_max_iterations: 迭代调研最大轮数(预算控制).
            research_max_follow_up_queries: 每轮缺口评估最多追加查询数.
            fact_check: 开启主动事实核查(提取关键陈述 → 交叉检索验证,
                仅矛盾打回; 复用 retriever/search); 默认关闭.
            max_claims_per_chapter: 每章最多核查的陈述条数(成本预算).
        """
        self._settings = settings or get_settings()
        self._llm = llm
        self._planner = Planner(llm, self._settings)
        self._researcher = Researcher(retriever, recaller, search)
        self._synthesizer = Synthesizer()
        self._writer = Writer(llm, self._settings)
        self._reviewer = Reviewer(
            llm,
            self._settings,
            retriever=retriever if fact_check else None,
            search=search if fact_check else None,
            max_claims_per_chapter=max_claims_per_chapter,
        )
        self._workspace_manager = workspace_manager
        self._iterative_research = iterative_research
        self._research_max_iterations = research_max_iterations
        self._research_max_follow_up_queries = research_max_follow_up_queries

    async def run(
        self,
        query: str,
        user_id: str = "anonymous",
        session_id: int | str | None = None,
        run_id: str | None = None,
        on_progress: Any | None = None,
    ) -> ReportResult:
        """执行完整流水线; 任一阶段失败返回 FAILED 结果(不抛出)."""
        rid = run_id or uuid4().hex[:12]
        try:
            await self._progress(on_progress, ReportStage.PLANNING, "生成报告大纲与检索计划")
            spec = await self._planner.plan(query)
            await self._progress(
                on_progress,
                ReportStage.PLANNING,
                f"大纲已生成: 标题「{spec.title}」, 共 {len(spec.chapters)} 个章节",
            )

            await self._progress(
                on_progress,
                ReportStage.RESEARCH,
                "并行调研: 知识库/记忆/联网",
            )
            # Self-RAG 式检索决策: needs_research=false 时跳过调研, 直接基于模型知识撰写
            if spec.needs_research:
                if self._iterative_research:
                    chapter_evidence = await self._researcher.research(
                        spec,
                        user_id,
                        iterative=True,
                        llm=self._llm,
                        max_iterations=self._research_max_iterations,
                        max_follow_up_queries=self._research_max_follow_up_queries,
                    )
                else:
                    chapter_evidence = await self._researcher.research(spec, user_id)
                evidence_count = sum(len(v) for v in chapter_evidence.values())
                await self._progress(
                    on_progress,
                    ReportStage.RESEARCH,
                    f"调研完成: 共收集 {evidence_count} 条证据",
                )
            else:
                chapter_evidence = {c: [] for c in spec.chapters}
                await self._progress(
                    on_progress,
                    ReportStage.RESEARCH,
                    "判定无需外部检索, 跳过调研, 直接基于模型知识撰写",
                )

            await self._progress(on_progress, ReportStage.SYNTHESIS, "证据融合: 去重与组织证据包")
            pack = self._synthesizer.synthesize(chapter_evidence)
            await self._progress(
                on_progress,
                ReportStage.SYNTHESIS,
                f"证据包就绪: {len(pack.evidence)} 条去重后证据",
            )

            await self._progress(on_progress, ReportStage.WRITING, "分章节并行撰写")
            chapters = await self._write_all(spec, pack)
            await self._progress(
                on_progress,
                ReportStage.WRITING,
                f"撰写完成: {len(chapters)} 个章节",
            )

            await self._progress(on_progress, ReportStage.REVIEW, "事实核查: 引用溯源与结论支持度")
            review = await self._reviewer.review(chapters, pack)
            rewritten = False
            if not review.passed:
                chapters = await self._rewrite_failed(chapters, pack, review)
                review = await self._reviewer.review(chapters, pack)
                rewritten = True
            await self._progress(
                on_progress,
                ReportStage.REVIEW,
                f"核查{'通过' if review.passed else '仍存在问题'}"
                f"({len(review.issues)} 项问题)" + (" · 已重写问题章节" if rewritten else ""),
            )

            references = self._render_references(pack.evidence)
            markdown = self._render_markdown(spec, chapters, references)
            path = await self._persist(markdown, rid, session_id)

            await self._progress(
                on_progress,
                ReportStage.DONE,
                f"报告完成, 落盘: {path or '(未落盘)'}",
            )
            return ReportResult(
                run_id=rid,
                spec=spec,
                evidence=pack.evidence,
                chapters=chapters,
                review=review,
                references=references,
                markdown_path=path,
            )
        except Exception as exc:
            logger.error("report.pipeline_failed", run_id=rid, error=str(exc))
            return ReportResult(
                run_id=rid,
                spec=ReportSpec(title=query.strip()[:40] or "研究报告"),
                stage=ReportStage.FAILED,
                error=str(exc),
            )

    # ── 阶段执行 ──

    async def _write_all(self, spec: ReportSpec, pack: EvidencePack) -> list[Chapter]:
        """分章节并行撰写(复用 run_concurrent: 超时 + 失败降级)."""
        if not spec.chapters:
            return []

        async def _one(chapter_title: str) -> SubtaskResult:
            evidence, base = self._chapter_evidence(pack, chapter_title)
            body = await self._writer.write_chapter(chapter_title, evidence, base)
            return SubtaskResult(
                subtask_id=chapter_title,
                success=bool(body),
                output=body,
                error=None if body else "章节撰写失败",
            )

        results = await run_concurrent(
            {title: _one(title) for title in spec.chapters},
            timeout=float(self._settings.agent_timeout_seconds),
        )
        return [Chapter(title=r.subtask_id, body=r.output) for r in results]

    async def _rewrite_failed(
        self,
        chapters: list[Chapter],
        pack: EvidencePack,
        review: Any,
    ) -> list[Chapter]:
        """审查不通过: 携带问题清单重写问题章节一次(其余章节不动)."""
        targets = {m.group(1) for m in (_ISSUE_CHAPTER_RE.match(i) for i in review.issues) if m}
        if not targets:
            return chapters
        rewritten: list[Chapter] = []
        for ch in chapters:
            if ch.title not in targets:
                rewritten.append(ch)
                continue
            evidence, base = self._chapter_evidence(pack, ch.title)
            issues = [i for i in review.issues if f"章节 '{ch.title}'" in i]
            body = await self._writer.write_chapter(ch.title, evidence, base, issues=issues)
            rewritten.append(Chapter(title=ch.title, body=body))
        logger.info("report.rewritten", chapters=sorted(targets))
        return rewritten

    @staticmethod
    def _chapter_evidence(pack: EvidencePack, chapter: str) -> tuple[list[Evidence], int]:
        """取章节证据列表(保序)与全局起始下标; 无证据时 base=1."""
        indexes = pack.chapter_index.get(chapter, [])
        evidence = [pack.evidence[i - 1] for i in indexes]
        return evidence, indexes[0] if indexes else 1

    # ── 产物渲染与落盘 ──

    @staticmethod
    def _render_references(evidence: list[Evidence]) -> list[str]:
        """参考文献表: 每证据一行, [n] 与正文引用一一对应."""
        out: list[str] = []
        for i, ev in enumerate(evidence, 1):
            if ev.doc_id is not None:
                out.append(
                    f"[{i}] 知识库文档: {ev.title or f'doc#{ev.doc_id}'} (doc_id={ev.doc_id})"
                )
            elif ev.url:
                out.append(f"[{i}] {ev.title or '网络来源'}: {ev.url}")
            else:
                out.append(f"[{i}] {ev.title or ev.source.value}: {ev.content[:60]}")
        return out

    @staticmethod
    def _render_markdown(spec: ReportSpec, chapters: list[Chapter], references: list[str]) -> str:
        """渲染报告 Markdown(标题 + 章节 + 参考文献表)."""
        lines: list[str] = [f"# {spec.title}", ""]
        for ch in chapters:
            lines += [f"## {ch.title}", "", ch.body, ""]
        lines += ["## 参考文献", ""]
        lines += references if references else ["(无引用证据)"]
        lines.append("")
        return "\n".join(lines)

    async def _persist(self, markdown: str, run_id: str, session_id: int | str | None) -> str:
        """报告落盘沙盒 sessions/{sid}/reports/{run_id}.md; 失败仅告警(不致命)."""
        try:
            wm = self._workspace_manager
            if wm is None:
                from knowflow.db.minio import get_minio
                from knowflow.sandbox.workspace import WorkspaceManager

                wm = WorkspaceManager(get_minio())
                self._workspace_manager = wm
            ops = wm.for_session(session_id or "default")
            return await ops.write(
                f"/workspace/reports/{run_id}.md",
                markdown.encode("utf-8"),
                "text/markdown",
            )
        except Exception as exc:
            logger.warning("report.persist_failed", run_id=run_id, error=str(exc))
            return ""

    @staticmethod
    async def _progress(on_progress: Any, stage: ReportStage, detail: str) -> None:
        """阶段进度回调(可空)."""
        if on_progress is not None:
            try:
                await on_progress(stage, detail)
            except Exception as exc:
                logger.warning("report.progress_callback_failed", error=str(exc))
