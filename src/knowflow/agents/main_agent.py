"""MainAgent - 意图理解/任务规划/结果汇总.

decide/act/observe 三步实现:
- decide: understand(规则意图分类) + plan(LLM 规划) → 是否委派
- act: 输出规划子任务(委派时)
- observe: 汇总子结果 / 无委派时直答

规划输出固定 JSON schema(见 agents/prompts.py), 解析失败重试 2 次后降级
为不委派(不阻塞对话).
"""

import re
from dataclasses import dataclass, field
from typing import Any

from knowflow.agents.base import BaseAgent
from knowflow.agents.prompts import PLANNER_PROMPT_TEMPLATE, SUMMARIZER_PROMPT_TEMPLATE
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

# 复杂任务信号词: 命中任一即进入规划流程(是否委派由 LLM 最终判断)
_COMPLEX_KEYWORDS = (
    "对比",
    "比较",
    "分别",
    "汇总",
    "总结",
    "分析",
    "差异",
    "优缺点",
    "同时查询",
    "有哪些",
)
# 多候选分隔符: 出现 >=2 次分隔视为存在多个并列对象(可能可拆分)
_CANDIDATE_SPLITTERS = ("、", "/", "和", "与", "vs", "VS")

# JSON 代码块包裹剥离(与 entity_extractor 同款容错)
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_MAX_PLAN_RETRIES = 2


@dataclass
class PlanResult:
    """任务规划结果."""

    needs_delegation: bool
    reason: str = ""
    subtasks: list[dict[str, Any]] = field(default_factory=list)


class MainAgent(BaseAgent):
    """主 Agent: 理解用户意图 → 规划子任务 → 汇总结果."""

    name = "main"
    role = "main"
    description = "主 Agent: 意图理解/任务规划/结果汇总"

    def __init__(self, llm: Any | None = None, settings: Any | None = None) -> None:
        super().__init__(llm, settings)
        self._last_plan: PlanResult | None = None

    # ── BaseAgent 三步循环 ──

    async def decide(self, state: dict[str, Any]) -> dict[str, Any]:
        """理解 + 规划, 决定是否需要委派."""
        query = state.get("query", "")
        intent = self.understand(query)
        if intent == "complex":
            plan = await self.plan(query)
        else:
            plan = PlanResult(needs_delegation=False, reason="简单任务无需委派")
        self._last_plan = plan
        return {
            "intent": intent,
            "needs_delegation": plan.needs_delegation,
            "plan": plan.subtasks,
        }

    async def act(self, state: dict[str, Any]) -> dict[str, Any]:
        """执行规划: 委派时输出子任务列表."""
        plan = self._last_plan
        if plan is not None and plan.needs_delegation:
            return {"plan": plan.subtasks}
        return {}

    async def observe(self, state: dict[str, Any]) -> dict[str, Any]:
        """观察结果: 有子结果则汇总, 否则直答."""
        query = state.get("query", "")
        results = state.get("subtask_results", [])
        context = state.get("retrieval_context", "")
        if results:
            answer = await self.summarize(query, results)
        else:
            answer = await self.direct_answer(query, context)
        return {"final_answer": answer}

    # ── 主 Agent 核心方法 ──

    @staticmethod
    def understand(query: str) -> str:
        """规则意图分类: complex(可能需委派) / simple(直连).

        命中复杂信号词, 或出现 >=2 个并列分隔符(多个候选对象)视为 complex.
        """
        if not query:
            return "simple"
        if any(k in query for k in _COMPLEX_KEYWORDS):
            return "complex"
        split_count = sum(query.count(s) for s in _CANDIDATE_SPLITTERS)
        return "complex" if split_count >= 2 else "simple"

    async def plan(self, query: str) -> PlanResult:
        """LLM 任务规划: 输出 needs_delegation + 可并发子任务列表."""
        prompt = PLANNER_PROMPT_TEMPLATE.format(
            query=query, max_subtasks=self._settings.agent_max_subtasks
        )
        llm = self._get_llm()

        last_error = ""
        for attempt in range(_MAX_PLAN_RETRIES + 1):
            try:
                response = await llm.ainvoke(prompt)
                data = _parse_json(_extract_text(response))
                needs_delegation = bool(data.get("needs_delegation", False))
                subtasks = [
                    _normalize_subtask(s, idx) for idx, s in enumerate(data.get("subtasks", []), 1)
                ]
                if needs_delegation and len(subtasks) < 2:
                    # 委派至少要 2 个子任务, 否则视为规划异常走降级
                    raise ValueError(f"委派模式下子任务数不足: {len(subtasks)}")
                return PlanResult(
                    needs_delegation=needs_delegation,
                    reason=str(data.get("reason", "")),
                    subtasks=subtasks,
                )
            except (ValueError, KeyError, TypeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "main_agent.plan_retry",
                    attempt=attempt + 1,
                    max_retries=_MAX_PLAN_RETRIES + 1,
                    error=last_error,
                )

        logger.warning("main_agent.plan_degraded", reason=last_error)
        return PlanResult(needs_delegation=False, reason=f"规划解析失败: {last_error}")

    async def summarize(self, query: str, results: list[dict[str, Any]]) -> str:
        """LLM 汇总子任务结果."""
        prompt = SUMMARIZER_PROMPT_TEMPLATE.format(
            query=query, subtask_results=_format_results(results)
        )
        response = await self._get_llm().ainvoke(prompt)
        return _extract_text(response).strip()

    async def direct_answer(self, query: str, context: str = "") -> str:
        """无委派时直接回答(注入检索上下文)."""
        system = (
            "你是 KnowFlow 企业知识库助手, 基于检索上下文回答问题, 不要编造事实.\n\n"
            f"检索上下文:\n{context}"
            if context
            else "你是 KnowFlow 企业知识库助手, 请直接回答问题."
        )
        messages = [{"role": "system", "content": system}, {"role": "user", "content": query}]
        response = await self._get_llm().ainvoke(messages)
        return _extract_text(response).strip()


# ── 解析工具 ──


def _extract_text(obj: Any) -> str:
    """从 LLM 响应提取文本: 兼容 str 与 langchain 消息对象."""
    if isinstance(obj, str):
        return obj
    content = getattr(obj, "content", None)
    return str(content) if content is not None else ""


def _parse_json(content: str) -> dict[str, Any]:
    """解析 LLM 输出为 JSON dict: 剥离代码块 + 截取 JSON 对象, 失败抛 ValueError."""
    if not content or not content.strip():
        raise ValueError("LLM 输出为空")

    import json

    match = _CODE_BLOCK_RE.search(content)
    if match:
        content = match.group(1)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"LLM 输出未找到 JSON 对象: {content[:100]}")
    content = content[start : end + 1]
    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {exc}; content={content[:100]}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"JSON 顶层不是对象: {type(result)}")
    return result


def _normalize_subtask(item: Any, index: int) -> dict[str, Any]:
    """规范化子任务条目: 校验 id/task 字段, 缺 id 时按序号兜底."""
    if not isinstance(item, dict):
        raise ValueError(f"子任务不是对象: {item}")
    task = str(item.get("task", "")).strip()
    if not task:
        raise ValueError("子任务缺少 task 字段")
    subtask_id = str(item.get("id", "")).strip() or f"t{index}"
    return {
        "id": subtask_id,
        "task": task,
        "description": str(item.get("description", "")).strip(),
    }


def _format_results(results: list[dict[str, Any]]) -> str:
    """子任务结果格式化为汇总 prompt 文本."""
    lines = []
    for r in results:
        tag = f"[{r.get('subtask_id', '?')}]"
        if r.get("success"):
            lines.append(f"{tag} {r.get('output', '')}")
        else:
            lines.append(f"{tag} (失败) {r.get('error', '')}")
    return "\n\n".join(lines) if lines else "(无子任务结果)"
