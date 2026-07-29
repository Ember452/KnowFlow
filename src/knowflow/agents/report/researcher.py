"""调研员 - 按章节检索计划执行三源检索(知识库/记忆/联网), 产出带出处证据.

默认单轮调研: 检索意图来自 Planner 的检索计划(每章 2-4 个查询), 每个查询并行
三源检索, 单源失败/无结果降级为空证据并告警, 不阻塞其他源与整体调研.

iterative=True 时升级为迭代调研(DeepSearch 范式): 初始查询 → 三源检索 →
LLM 缺口评估(信息是否足以撰写章节) → 不足则生成追加查询再检索, 最多
max_iterations 轮; LLM 评估失败/解析失败降级为停止迭代(不阻塞).
"""

import asyncio
import json
import re
from collections.abc import Callable
from typing import Any

from knowflow.agents.report.models import ChapterPlan, Evidence, EvidenceSource, ReportSpec
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_PER_QUERY_TOP_K = 3  # 每个查询每源最多取证据数(控制证据包规模)
_EVIDENCE_SUFFICIENT_THRESHOLD = 12  # 章节证据条数兜底阈值(防止 LLM 一直判不足)
_GAP_EVIDENCE_CAP = 10  # 缺口评估注入的证据条数上限(控制 prompt 规模)
_GAP_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_GAP_ASSESS_PROMPT = (
    "你是 KnowFlow 调研缺口评估员. 判断已有证据是否足以撰写章节「{chapter}」.\n"
    "已有证据:\n{evidence}\n\n"
    '严格输出 JSON: {{"sufficient": true/false, "gap": "一句话说明缺口", '
    '"follow_up_queries": ["追加查询1", ...]}}\n'
    "规则: sufficient=true 时 follow_up_queries 必须为空数组; "
    "follow_up_queries 最多 {max_queries} 条, 必须具体(含主题词), 不能与已有查询重复.\n"
    "只输出 JSON, 不要任何其他文字."
)


class Researcher:
    """调研员: 三源检索聚合为章节证据."""

    def __init__(
        self,
        retriever: Any | None = None,
        recaller: Any | None = None,
        search: Any | None = None,
        per_query_top_k: int = _PER_QUERY_TOP_K,
    ) -> None:
        """初始化.

        Args:
            retriever: 知识库检索器(实现 async retrieve(query, top_k) -> RetrievalResult).
            recaller: 记忆召回器(实现 async recall(query, user_id, top_k)); None 跳过记忆源.
            search: 联网搜索器(BaseTool 实例(execute) 或 callable(query, max_results));
                None 跳过联网源.
            per_query_top_k: 每个查询每源最多证据数.
        """
        self._retriever = retriever
        self._recaller = recaller
        self._search = search
        self._per_query_top_k = per_query_top_k

    async def research(
        self,
        spec: ReportSpec,
        user_id: str = "anonymous",
        *,
        iterative: bool = False,
        llm: Any | None = None,
        max_iterations: int = 2,
        max_follow_up_queries: int = 3,
    ) -> dict[str, list[Evidence]]:
        """按检索计划调研全部章节; 返回 {章节标题: 证据列表}(章节间并发, 单章失败降级为空).

        iterative=False(默认)时单轮执行 Planner 检索计划; iterative=True 时每章走
        迭代调研(缺口评估 + 追加查询, 最多 max_iterations 轮).
        """
        if not iterative:
            return await self._research_single(spec, user_id)

        if llm is None:
            from knowflow.core.llm import get_chat_llm

            llm = get_chat_llm()

        async def _one(plan: ChapterPlan) -> tuple[str, list[Evidence]]:
            try:
                return plan.chapter, await self.research_chapter_iterative(
                    plan, user_id, llm, max_iterations, max_follow_up_queries
                )
            except Exception as exc:
                logger.warning(
                    "report.research_chapter_iterative_failed",
                    chapter=plan.chapter,
                    error=str(exc),
                )
                return plan.chapter, []

        results = await asyncio.gather(*(_one(p) for p in spec.research_plan))
        return dict(results)

    async def _research_single(
        self, spec: ReportSpec, user_id: str = "anonymous"
    ) -> dict[str, list[Evidence]]:
        """单轮调研: 逐章节执行 Planner 检索计划(章节间并发, 单章失败降级为空)."""
        if not spec.research_plan:
            return {c: [] for c in spec.chapters}

        async def _one(plan: ChapterPlan) -> tuple[str, list[Evidence]]:
            try:
                return plan.chapter, await self.research_chapter(plan, user_id)
            except Exception as exc:
                logger.warning(
                    "report.research_chapter_failed", chapter=plan.chapter, error=str(exc)
                )
                return plan.chapter, []

        results = await asyncio.gather(*(_one(p) for p in spec.research_plan))
        return dict(results)

    async def research_chapter_iterative(
        self,
        plan: ChapterPlan,
        user_id: str,
        llm: Any,
        max_iterations: int,
        max_follow_up_queries: int,
    ) -> list[Evidence]:
        """迭代调研单章节: 初始查询 → 三源检索 → LLM 缺口评估 → 追加查询再检索.

        预算控制: 最多 max_iterations 轮, 证据条数达阈值即停止; 已执行过的查询
        不再重复检索; LLM 评估失败/判定足够/无追加查询时提前停止(降级不阻塞).
        """
        evidence: list[Evidence] = []
        queries = [q.strip() for q in plan.queries if q.strip()]
        executed: set[str] = set()
        iteration = 0
        while queries and iteration < max_iterations:
            iteration += 1
            for query in queries:
                executed.add(query)
                evidence.extend(await self._query_three_sources(query, user_id))
            if len(evidence) >= _EVIDENCE_SUFFICIENT_THRESHOLD:
                break
            gap = await self._assess_gap(plan.chapter, evidence, llm, max_follow_up_queries)
            if gap is None:
                break  # LLM 评估失败降级: 停止迭代, 使用已有证据
            if gap.get("sufficient"):
                break
            follow_ups = [q.strip() for q in gap.get("follow_up_queries") or [] if q.strip()]
            queries = [q for q in follow_ups if q not in executed]
        return evidence

    async def _assess_gap(
        self, chapter: str, evidence: list[Evidence], llm: Any, max_queries: int
    ) -> dict[str, Any] | None:
        """LLM 缺口评估: 返回 sufficient/follow_up_queries; 失败/解析失败返回 None."""
        try:
            evidence_lines = "\n".join(f"- {e.content[:200]}" for e in evidence[:_GAP_EVIDENCE_CAP])
            prompt = _GAP_ASSESS_PROMPT.format(
                chapter=chapter,
                evidence=evidence_lines or "(暂无证据)",
                max_queries=max_queries,
            )
            response = await llm.ainvoke(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"请评估章节「{chapter}」的证据覆盖情况."},
                ]
            )
            text = _extract_text(response)
            return _parse_gap_json(text)
        except Exception as exc:
            logger.warning("report.research_gap_assess_failed", chapter=chapter, error=str(exc))
            return None

    async def research_chapter(
        self, plan: ChapterPlan, user_id: str = "anonymous"
    ) -> list[Evidence]:
        """调研单个章节: 对每个查询做三源检索, 合并为章节证据."""
        evidence: list[Evidence] = []
        for query in plan.queries:
            if not query.strip():
                continue
            evidence.extend(await self._query_three_sources(query, user_id))
        return evidence

    async def _query_three_sources(self, query: str, user_id: str) -> list[Evidence]:
        """单查询三源并行检索; 各源失败独立降级."""
        sources: list[Any] = [
            self._search_knowledge(query),
        ]
        if self._recaller is not None:
            sources.append(self._search_memory(query, user_id))
        if self._search is not None:
            sources.append(self._search_web(query))
        results = await asyncio.gather(*sources, return_exceptions=True)
        out: list[Evidence] = []
        for res in results:
            if isinstance(res, BaseException):
                logger.warning("report.research_source_failed", error=str(res))
                continue
            out.extend(res)
        return out

    async def _search_knowledge(self, query: str) -> list[Evidence]:
        """知识库混合检索(带 doc_id/doc_title 出处)."""
        if self._retriever is None:
            return []
        result = await self._retriever.retrieve(query, top_k=self._per_query_top_k)
        return [
            Evidence(
                source=EvidenceSource.KNOWLEDGE,
                content=getattr(chunk, "content", "") or "",
                title=getattr(chunk, "doc_title", None) or "",
                doc_id=getattr(chunk, "doc_id", None),
                score=getattr(chunk, "score", 0.0) or 0.0,
            )
            for chunk in getattr(result, "chunks", [])
        ]

    async def _search_memory(self, query: str, user_id: str) -> list[Evidence]:
        """长期记忆召回."""
        assert self._recaller is not None  # 调用方已判非 None
        hits = await self._recaller.recall(query, user_id, top_k=self._per_query_top_k)
        return [
            Evidence(
                source=EvidenceSource.MEMORY,
                content=h.content,
                title="长期记忆",
                score=h.score,
            )
            for h in hits
        ]

    async def _search_web(self, query: str) -> list[Evidence]:
        """联网搜索(duckduckgo 等); 结果带标题/摘要/链接."""
        results = await self._invoke_search(query)
        return [
            Evidence(
                source=EvidenceSource.WEB,
                content=str(item.get("snippet") or item.get("body") or ""),
                title=str(item.get("title") or ""),
                url=str(item.get("url") or item.get("href") or ""),
            )
            for item in results
        ]

    async def _invoke_search(self, query: str) -> list[dict[str, Any]]:
        """调用搜索器, 兼容 BaseTool(execute) 与 callable 两种形态."""
        search: Any = self._search
        if search is None:
            return []
        if hasattr(search, "execute"):
            result = await search.execute(query=query, max_results=self._per_query_top_k)
            if not result.success:
                raise RuntimeError(f"联网搜索失败: {result.error}")
            return list(result.output.get("results", []) if isinstance(result.output, dict) else [])
        fn: Callable[..., Any] = search
        results = await fn(query, max_results=self._per_query_top_k)
        return [dict(item) for item in results]


def _extract_text(obj: Any) -> str:
    """从 LLM 响应提取文本: 兼容 str / dict(content) / 带 .content 的对象."""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        content = obj.get("content")
        return content if isinstance(content, str) else str(content or "")
    content = getattr(obj, "content", None)
    return content if isinstance(content, str) else str(content or "")


def _parse_gap_json(text: str) -> dict[str, Any]:
    """解析缺口评估 JSON; 结构不合法抛 ValueError(触发降级)."""
    match = _GAP_JSON_RE.search(text)
    if match is None:
        raise ValueError("缺口评估输出未找到 JSON 对象")
    raw = json.loads(match.group(0))
    if not isinstance(raw, dict):
        raise ValueError("缺口评估 JSON 顶层不是对象")
    follow_ups = raw.get("follow_up_queries")
    if not isinstance(follow_ups, list):
        raise ValueError("缺口评估缺少 follow_up_queries 数组")
    return {
        "sufficient": bool(raw.get("sufficient", False)),
        "gap": str(raw.get("gap", "")),
        "follow_up_queries": [str(q) for q in follow_ups],
    }
