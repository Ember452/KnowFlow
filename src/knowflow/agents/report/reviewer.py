"""事实核查器 - 双校验: 规则校验(引用可定位/章节完整) + LLM 结论支持度校验.

规则校验是确定性检查(引用下标越界/正文过短), 不通过即打回;
LLM 校验判断结论是否被所引证据支持, 解析失败默认通过(容错, 不阻塞流水线).

注入 retriever/search 后启用主动事实核查(轻量版): 从章节正文提取关键陈述
(含数值/事实性断言), 用陈述作为查询交叉检索验证, 判定支持/矛盾/证据不足;
仅"矛盾"打回, "证据不足"降级为告警不阻塞. 提取/验证失败均降级跳过.
"""

import asyncio
import json
import re
from typing import Any

from knowflow.agents.report.models import Chapter, EvidencePack, ReviewResult
from knowflow.agents.report.planner import _extract_text
from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_MIN_BODY_CHARS = 30  # 章节正文最短字符数(过短视为无效输出)
_CITATION_RE = re.compile(r"\[(\d+)\]")
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# 主动事实核查预算(轻量版成本控制)
_CLAIM_QUERY_CHARS = 100  # 陈述直接作为检索查询时的截断长度
_VERIFY_EVIDENCE_CHARS = 300  # 单条验证证据注入 prompt 的截断长度

_CLAIM_EXTRACT_PROMPT = (
    "你是 KnowFlow 陈述提取员. 从章节正文中提取需要事实核查的关键陈述"
    "(含具体数值/日期/事实性断言), 最多 {max_claims} 条, 按重要性排序.\n"
    '严格输出 JSON: {{"claims": ["陈述1", "陈述2"]}}\n'
    "没有需要核查的陈述时输出空数组. 只输出 JSON."
)

_VERIFY_PROMPT = (
    "你是 KnowFlow 事实核查员. 判断陈述是否被检索到的证据支持.\n"
    "陈述: {claim}\n\n检索证据:\n{evidence}\n\n"
    '严格输出 JSON: {{"verdict": "supported"|"contradicted"|"unverified", '
    '"reason": "一句话说明"}}\n'
    "verdict 含义: supported=证据支持该陈述; contradicted=证据与陈述矛盾; "
    "unverified=证据不足无法确认. 只输出 JSON."
)

_REVIEWER_SYSTEM_PROMPT = (
    "你是 KnowFlow 报告审查员. 判断章节结论是否被所引证据支持.\n"
    "证据素材以 [n] 标注(全局下标), 章节正文中的 [n] 引用对应同下标证据.\n"
    '严格输出 JSON: {"passed": true/false, "issues": ["问题1", ...]}\n'
    "检查要点: ① 正文结论是否有证据支撑(引用是否与结论相关); ② 是否有正文声明与证据矛盾;\n"
    "③ 证据不足的断言要指出. 只输出 JSON."
)


def extract_citations(body: str) -> list[int]:
    """提取正文 [n] 引用下标(去重保序)."""
    return [int(m) for m in _CITATION_RE.findall(body)]


class ReviewRuleChecker:
    """规则校验: 引用可定位 + 章节完整(确定性, 可单测)."""

    def check(self, chapters: list[Chapter], evidence_count: int) -> list[str]:
        """返回问题清单; 空列表 = 通过."""
        issues: list[str] = []
        for ch in chapters:
            if len(ch.body.strip()) < _MIN_BODY_CHARS:
                issues.append(f"章节 '{ch.title}' 内容过短({len(ch.body.strip())} 字符)")
            for n in extract_citations(ch.body):
                if n < 1 or n > evidence_count:
                    issues.append(
                        f"章节 '{ch.title}' 引用 [{n}] 越界(证据包仅 1..{evidence_count})"
                    )
        return issues


class ActiveFactChecker:
    """主动事实核查(轻量版): 提取关键陈述 → 检索交叉验证 → 判定.

    成本控制: 每章最多 max_claims_per_chapter 条陈述、每条 1 次检索(top_k=verify_top_k);
    陈述直接作为检索查询(截断), 不额外生成查询; 仅"矛盾"返回问题清单,
    "证据不足"降级为告警; 提取/检索/判定任一环节失败均跳过(容错, 不阻塞).
    """

    def __init__(
        self,
        llm: Any | None = None,
        retriever: Any | None = None,
        search: Any | None = None,
        max_claims_per_chapter: int = 3,
        verify_top_k: int = 3,
    ) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake; None 时懒加载主模型.
            retriever: 知识库检索器(实现 async retrieve); None 且无 search 时跳过核查.
            search: 联网搜索器(BaseTool.execute 或 callable(query, max_results)).
            max_claims_per_chapter: 每章最多核查的陈述条数(成本预算).
            verify_top_k: 每条陈述检索取回的验证证据数.
        """
        self._llm = llm
        self._retriever = retriever
        self._search = search
        self._max_claims_per_chapter = max_claims_per_chapter
        self._verify_top_k = verify_top_k

    def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from knowflow.core.llm import get_chat_llm

        return get_chat_llm()

    async def check(self, chapters: list[Chapter], user_id: str = "anonymous") -> list[str]:
        """逐章节主动核查, 返回问题清单(仅"矛盾"陈述); 各环节失败降级跳过."""
        issues: list[str] = []
        for ch in chapters:
            claims = await self._extract_claims(ch.body)
            for claim in claims:
                verdict, reason = await self._verify_claim(claim, user_id)
                if verdict == "contradicted":
                    issues.append(f"章节 '{ch.title}': 陈述「{claim}」与检索证据矛盾({reason})")
                elif verdict == "unverified":
                    logger.warning(
                        "report.fact_check_unverified",
                        chapter=ch.title,
                        claim=claim[:60],
                    )
        return issues

    async def _extract_claims(self, body: str) -> list[str]:
        """LLM 提取关键陈述; 失败/解析失败返回空(降级跳过核查)."""
        try:
            prompt = _CLAIM_EXTRACT_PROMPT.format(max_claims=self._max_claims_per_chapter)
            response = await self._get_llm().ainvoke(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"章节正文:\n{body}"},
                ]
            )
            raw = _parse_json_object(_extract_text(response))
            claims = [str(c).strip() for c in raw.get("claims") or [] if str(c).strip()]
            return claims[: self._max_claims_per_chapter]
        except Exception as exc:
            logger.warning("report.fact_check_extract_failed", error=str(exc))
            return []

    async def _verify_claim(self, claim: str, user_id: str) -> tuple[str, str]:
        """单条陈述交叉验证: 检索证据 → LLM 判定; 无源/失败降级 unverified."""
        evidence_text = await self._gather_evidence(claim, user_id)
        if not evidence_text:
            return "unverified", "无检索证据可验证"
        try:
            prompt = _VERIFY_PROMPT.format(claim=claim, evidence=evidence_text)
            response = await self._get_llm().ainvoke(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"请判定陈述: {claim}"},
                ]
            )
            raw = _parse_json_object(_extract_text(response))
            verdict = str(raw.get("verdict", ""))
            if verdict not in ("supported", "contradicted", "unverified"):
                raise ValueError(f"verdict 非法: {verdict}")
            return verdict, str(raw.get("reason", ""))
        except Exception as exc:
            logger.warning("report.fact_check_verify_failed", error=str(exc))
            return "unverified", "验证判定失败"

    async def _gather_evidence(self, claim: str, user_id: str) -> str:
        """用陈述本身作为查询做知识库/联网检索, 返回合并证据文本; 失败降级为空."""
        del user_id
        query = claim[:_CLAIM_QUERY_CHARS]
        lines: list[str] = []
        if self._retriever is not None:
            try:
                result = await self._retriever.retrieve(query, top_k=self._verify_top_k)
                lines.extend(
                    str(getattr(c, "content", "") or "") for c in getattr(result, "chunks", [])
                )
            except Exception as exc:
                logger.warning("report.fact_check_retrieve_failed", error=str(exc))
        if self._search is not None:
            try:
                results = await self._invoke_search(query)
                lines.extend(str(item.get("snippet") or item.get("body") or "") for item in results)
            except Exception as exc:
                logger.warning("report.fact_check_search_failed", error=str(exc))
        return "\n".join(f"- {line[:_VERIFY_EVIDENCE_CHARS]}" for line in lines if line)

    async def _invoke_search(self, query: str) -> list[dict[str, Any]]:
        """调用联网搜索器, 兼容 BaseTool(execute) 与 callable 两种形态."""
        search: Any = self._search
        if hasattr(search, "execute"):
            result = await search.execute(query=query, max_results=self._verify_top_k)
            if not result.success:
                raise RuntimeError(f"联网搜索失败: {result.error}")
            return list(result.output.get("results", []) if isinstance(result.output, dict) else [])
        results = await search(query, max_results=self._verify_top_k)
        return [dict(item) for item in results]


class Reviewer:
    """事实核查: 规则校验 + LLM 支持度校验 + 主动事实核查(可选)."""

    def __init__(
        self,
        llm: Any | None = None,
        settings: Settings | None = None,
        retriever: Any | None = None,
        search: Any | None = None,
        max_claims_per_chapter: int = 3,
        verify_top_k: int = 3,
    ) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake; None 时懒加载主模型.
            settings: Settings 单例.
            retriever: 主动核查用知识库检索器; None 且无 search 时跳过主动核查.
            search: 主动核查用联网搜索器; None 且无 retriever 时跳过主动核查.
            max_claims_per_chapter: 每章最多核查的陈述条数(成本预算).
            verify_top_k: 每条陈述检索取回的验证证据数.
        """
        self._llm = llm
        self._settings = settings or get_settings()
        self._rules = ReviewRuleChecker()
        self._fact_checker: ActiveFactChecker | None
        if retriever is not None or search is not None:
            self._fact_checker = ActiveFactChecker(
                llm,
                retriever,
                search,
                max_claims_per_chapter=max_claims_per_chapter,
                verify_top_k=verify_top_k,
            )
        else:
            self._fact_checker = None

    def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from knowflow.core.llm import get_chat_llm

        return get_chat_llm()

    async def review(self, chapters: list[Chapter], pack: EvidencePack) -> ReviewResult:
        """递进式三阶段核查: 规则 → LLM 支持度 → 主动事实核查(可选).

        规则不通过直接打回(不调 LLM); 支持度不通过打回(省主动核查成本);
        全部通过且注入检索源时, 再做主动交叉验证(仅矛盾打回).
        证据包为空(needs_research=false 跳过检索)时跳过依赖证据的两阶段校验,
        仅保留规则校验(正文过短/引用越界), 与无检索模式语义一致.
        """
        rule_issues = self._rules.check(chapters, len(pack.evidence))
        if rule_issues:
            return ReviewResult(passed=False, issues=rule_issues)
        if not chapters:
            return ReviewResult(passed=False, issues=["报告无章节产出"])
        if not pack.evidence:
            return ReviewResult(passed=True, issues=[])
        support_issues = await self._llm_support_check(chapters, pack)
        if support_issues:
            return ReviewResult(passed=False, issues=support_issues)
        if self._fact_checker is not None:
            fact_issues = await self._fact_checker.check(chapters)
            if fact_issues:
                return ReviewResult(passed=False, issues=fact_issues)
        return ReviewResult(passed=True, issues=[])

    async def _llm_support_check(self, chapters: list[Chapter], pack: EvidencePack) -> list[str]:
        """逐章节 LLM 校验; 单章节失败/解析失败默认通过(容错)."""
        issues: list[str] = []
        results = await asyncio.gather(
            *(self._check_one(ch, pack) for ch in chapters),
            return_exceptions=True,
        )
        for ch, res in zip(chapters, results, strict=True):
            if isinstance(res, BaseException):
                logger.warning("report.review_llm_failed", chapter=ch.title, error=str(res))
                continue
            issues.extend(res)
        return issues

    async def _check_one(self, chapter: Chapter, pack: EvidencePack) -> list[str]:
        """校验单章节: LLM 判断结论支持度, 返回该章问题清单."""
        cited = sorted({n for n in extract_citations(chapter.body) if 1 <= n <= len(pack.evidence)})
        evidence_lines = "\n".join(
            f"[{n}] [{pack.evidence[n - 1].source.value}] {pack.evidence[n - 1].content}"
            for n in cited
        )
        response = await self._get_llm().ainvoke(
            [
                {"role": "system", "content": _REVIEWER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"章节标题: {chapter.title}\n\n章节正文:\n{chapter.body}\n\n"
                        f"被引用的证据素材:\n{evidence_lines}"
                    ),
                },
            ]
        )
        issues = self._parse_review_json(_extract_text(response))
        return [f"章节 '{chapter.title}': {issue}" for issue in issues]

    @staticmethod
    def _parse_review_json(text: str) -> list[str]:
        """解析审查 JSON; 非 JSON/解析失败返回空(视为通过, 容错)."""
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match is None:
            return []
        import json

        try:
            raw = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            logger.warning("report.review_json_invalid", error=str(exc))
            return []
        if raw.get("passed") is True:
            return []
        issues = raw.get("issues")
        return [str(i) for i in issues] if isinstance(issues, list) else []


def _parse_json_object(text: str) -> dict[str, Any]:
    """解析 JSON 对象文本为 dict; 失败抛异常(由调用方降级处理)."""
    match = _JSON_RE.search(text)
    if match is None:
        raise ValueError("输出未找到 JSON 对象")
    raw = json.loads(match.group(0))
    if not isinstance(raw, dict):
        raise ValueError("JSON 顶层不是对象")
    return raw
