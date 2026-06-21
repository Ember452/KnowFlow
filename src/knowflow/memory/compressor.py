"""长期记忆压缩 - LLM 摘要 + 关键信息提取, 避免记忆无限膨胀.

对多条高价值记忆做合并压缩, 产出结构化摘要(保留事实/偏好, 去除寒暄).
LLM 失败时回退规则拼接截断, 保证流程不中断.
"""

from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_MAX_ITEMS = 20  # 单次压缩最多处理的记忆条数
_FALLBACK_CHARS = 200  # 兜底时每条记忆保留的字符数

_SYSTEM_PROMPT = (
    "你是用户画像整理助手. 将多条用户记忆合并压缩为简洁画像摘要: "
    "保留偏好/习惯/身份/目标等事实, 去除寒暄与重复, 用分号分隔要点. "
    "只输出摘要正文, 不要其他说明."
)


class Compressor:
    """长期记忆压缩器. llm 需实现 ainvoke(messages) 并返回文本或含 content 的对象."""

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    @staticmethod
    def _extract_text(obj: Any) -> str:
        if isinstance(obj, str):
            return obj
        content = getattr(obj, "content", None)
        return str(content) if content is not None else ""

    async def compress(self, memories: list[str]) -> str:
        """压缩多条记忆为一条摘要. 输入为空返回空串."""
        if not memories:
            return ""
        items = memories[:_MAX_ITEMS]
        if self._llm is not None:
            try:
                user_prompt = "\n".join(f"- {m}" for m in items)
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
                logger.warning("memory.compress_fallback", error=str(exc))
        # 兜底: 每条截断拼接, 保证压缩流程不中断
        return "; ".join(m[:_FALLBACK_CHARS] for m in items)
