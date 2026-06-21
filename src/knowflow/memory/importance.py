"""信息重要性打分 - LLM 0-10 分 + 规则兜底.

LLM 输出 JSON 分数; 无 LLM/调用失败时用规则兜底: 偏好类关键词高置信,
身份/目标类中置信, 普通寒暄低置信, 长度加成. 规则兜底保证离线可测.
"""

import json
import re
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)

# 高置信关键词: 明确偏好/习惯/承诺(8-10 分)
_HIGH_KEYWORDS = ("请记住", "我喜欢", "我偏好", "我的习惯", "请不要", "我总是", "我从不", "以后都")
# 中置信关键词: 身份/目标/经历(5-7 分)
_MID_KEYWORDS = ("我是", "我在", "我来自", "我希望", "我的目标是", "我负责")

_SYSTEM_PROMPT = (
    "你判断用户消息中是否有值得跨会话记住的信息(偏好/习惯/身份/长期目标). "
    '输出 JSON: {"importance": 0-10 的整数}. 只输出 JSON, 不要其他内容.'
)


class ImportanceScorer:
    """消息重要性打分器. llm 需实现 ainvoke(messages) 并返回文本或含 content 的对象."""

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    async def score(self, text: str) -> float:
        """对消息打分(0-10). LLM 失败时回退规则打分."""
        if not text:
            return 0.0
        if self._llm is not None:
            try:
                response = await self._llm.ainvoke(
                    [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": f"用户消息: {text}"},
                    ]
                )
                score = self._parse_score(response)
                if score is not None:
                    return score
            except Exception as exc:
                logger.warning("memory.importance_fallback", error=str(exc))
        return self.rule_score(text)

    @staticmethod
    def _parse_score(obj: Any) -> float | None:
        """从 LLM 响应解析分数; 无法解析返回 None."""
        content = obj if isinstance(obj, str) else getattr(obj, "content", None)
        if not content:
            return None
        match = re.search(r"\{\s*\"importance\"\s*:\s*([\d.]+)", str(content))
        if match:
            try:
                return max(0.0, min(10.0, float(match.group(1))))
            except ValueError:
                return None
        try:
            data = json.loads(str(content))
            return max(0.0, min(10.0, float(data["importance"])))
        except (ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def rule_score(text: str) -> float:
        """规则兜底打分(纯函数, 离线可测)."""
        score = 0.0
        if any(kw in text for kw in _HIGH_KEYWORDS):
            score = 9.0
        elif any(kw in text for kw in _MID_KEYWORDS):
            score = 6.0
        else:
            score = 2.0
        # 长度加成: 长消息通常信息量更高
        if len(text) > 100:
            score = min(10.0, score + 1.0)
        return score
