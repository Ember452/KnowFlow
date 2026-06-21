"""LLM 历史摘要 - 增量 compact, 保留关键信息清单.

超预算时用摘要替代全量历史: 旧摘要 + 新消息 → 新摘要, 避免重复压缩.
LLM 失败时回退规则抽取(每条消息截断拼接), 保证流程不中断.
"""

from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)

# 每条消息规则抽取的最大字符数(兜底用)
_FALLBACK_MSG_CHARS = 80

_SYSTEM_PROMPT = (
    "你是对话历史摘要助手. 将对话压缩为简洁摘要, 保留关键信息: "
    "用户偏好、事实性陈述、已确认的决策与约定. 只输出摘要正文, 不要其他说明."
)


class Summarizer:
    """对话历史摘要器. llm 需实现 ainvoke(messages) 并返回文本或含 content 的对象."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    @staticmethod
    def _extract_text(obj: Any) -> str:
        """从 LLM 响应提取文本: 兼容 str 与 langchain 消息对象."""
        if isinstance(obj, str):
            return obj
        content = getattr(obj, "content", None)
        return str(content) if content is not None else ""

    async def summarize(
        self,
        history: list[dict[str, str]],
        previous_summary: str | None = None,
    ) -> str:
        """生成/更新摘要.

        Args:
            history: 最近轮次的消息列表(role/content).
            previous_summary: 旧摘要(增量 compact 时传入), 可为空.

        Returns:
            摘要文本; 输入为空时返回旧摘要或空串.
        """
        if not history:
            return previous_summary or ""
        parts = [f"{m['role']}: {m['content']}" for m in history]
        user_prompt = "历史消息:\n" + "\n".join(parts)
        if previous_summary:
            user_prompt = f"旧摘要:\n{previous_summary}\n\n新增消息:\n" + "\n".join(parts)
        try:
            response = await self._llm.ainvoke(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
            text = self._extract_text(response).strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("context.summarize_fallback", error=str(exc))
        # 兜底: 规则抽取关键信息, 保证摘要流程不中断
        return self._rule_fallback(parts)

    @staticmethod
    def _rule_fallback(parts: list[str]) -> str:
        """规则兜底: 截取每条消息前 N 字符拼接."""
        return "; ".join(p[:_FALLBACK_MSG_CHARS] for p in parts[-8:])
