"""报告规划器 - LLM 生成报告大纲(章节 + 每章检索计划).

prompt 注入可用信息源清单(知识库/记忆/联网)与引用规范, 要求输出 JSON 大纲;
解析失败回退默认大纲(标题 + 单章节 + 3 个检索查询), 保证流水线可跑.
"""

import json
import re
from typing import Any

from knowflow.agents.base import BaseAgent
from knowflow.agents.report.models import ChapterPlan, ReportSpec
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_PLANNER_SYSTEM_PROMPT = (
    "你是 KnowFlow 研究报告规划师. 根据用户需求输出报告大纲, 严格输出 JSON, 格式:\n"
    '{"title": "报告标题", "needs_research": true/false, "chapters": '
    '[{"title": "章节标题", "queries": ["检索查询1", "检索查询2"]}]}\n'
    "要求:\n"
    "- 3-6 个章节, 覆盖背景/现状/分析/结论等维度;\n"
    "- 每章节 2-4 个检索查询, 用于知识库检索/记忆召回/联网搜索;\n"
    "- 查询要具体(含主题词), 不要泛泛的'相关资料';\n"
    "- needs_research 表示报告是否需要检索外部信息(知识库/记忆/联网)支撑: "
    "涉及具体事实/数据/文档内容时为 true; "
    "纯通用知识/主观分析/基于模型已有知识即可完成为 false; "
    "needs_research=false 时 queries 可留空.\n"
    "只输出 JSON, 不要任何其他文字."
)

_FALLBACK_QUERY_SUFFIXES = ("背景与现状", "关键信息与数据", "结论与展望")


def _extract_text(response: Any) -> str:
    """从 LLM 响应提取文本(兼容 str / dict(content) / 带 .content 的对象)."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        content = response.get("content")
        return content if isinstance(content, str) else str(content or "")
    content = getattr(response, "content", None)
    return content if isinstance(content, str) else str(content or "")


def _parse_spec(text: str) -> ReportSpec | None:
    """从 LLM 输出解析 ReportSpec; 结构不合法返回 None(触发回退)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match is None:
        return None
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        logger.warning("report.planner_json_invalid", error=str(exc))
        return None
    title = str(raw.get("title", "")).strip()
    chapters = raw.get("chapters")
    if not title or not isinstance(chapters, list) or not chapters:
        return None
    plan: list[ChapterPlan] = []
    titles: list[str] = []
    for item in chapters:
        if not isinstance(item, dict):
            continue
        chapter_title = str(item.get("title", "")).strip()
        queries_raw = item.get("queries")
        queries = (
            [str(q).strip() for q in queries_raw if str(q).strip()]
            if isinstance(queries_raw, list)
            else []
        )
        if chapter_title:
            titles.append(chapter_title)
            plan.append(ChapterPlan(chapter=chapter_title, queries=queries))
    if not titles:
        return None
    # needs_research 参照 Self-RAG retrieve 决策; 缺失/非法默认 true(检索兜底)
    needs_research = raw.get("needs_research", True)
    if not isinstance(needs_research, bool):
        needs_research = True
    return ReportSpec(
        title=title, chapters=titles, research_plan=plan, needs_research=needs_research
    )


class Planner(BaseAgent):
    """报告规划器: 生成标题 + 章节 + 每章检索计划."""

    name = "report_planner"
    role = "main"
    description = "报告规划: 拆解需求为大纲与检索计划"

    async def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        """直接执行规划."""
        return {"action": "execute"}

    async def act(self, state: dict[str, Any]) -> dict[str, Any]:
        """生成报告规格."""
        query = str(state.get("query", ""))
        spec = await self.plan(query)
        return {"spec": spec}

    async def observe(self, state: dict[str, Any]) -> dict[str, Any]:
        """返回规划结果."""
        return {"spec": state.get("spec")}

    async def plan(self, query: str) -> ReportSpec:
        """生成报告规格; LLM 不可用/解析失败回退默认大纲."""
        if query.strip():
            try:
                response = await self._get_llm().ainvoke(
                    [
                        {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                        {"role": "user", "content": f"用户需求: {query}"},
                    ]
                )
                spec = _parse_spec(_extract_text(response))
                if spec is not None:
                    logger.info("report.planned", title=spec.title, chapters=len(spec.chapters))
                    return spec
            except Exception as exc:
                logger.warning("report.planner_failed", error=str(exc))
        return self._fallback_spec(query)

    @staticmethod
    def _fallback_spec(query: str) -> ReportSpec:
        """回退大纲: 标题取需求前 40 字, 单章节 + 3 个查询变体."""
        title = query.strip()[:40] or "研究报告"
        queries = [f"{query} {suffix}" for suffix in _FALLBACK_QUERY_SUFFIXES]
        return ReportSpec(
            title=title,
            chapters=[title],
            research_plan=[ChapterPlan(chapter=title, queries=queries)],
        )
