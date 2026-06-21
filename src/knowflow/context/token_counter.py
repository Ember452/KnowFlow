"""Token 计数 - tiktoken 精确计数, 模型不可用时回退字符/4 估算.

供上下文预算/卸载阈值判定使用. 模型名映射失败时回退估算, 保证任何环境可用.
"""

from functools import lru_cache
from typing import Any

from knowflow.core.config import Settings, get_settings


@lru_cache
def _load_encoding(model: str) -> Any | None:
    """按模型取 tiktoken 编码, 失败返回 None(调用方回退字符估算)."""
    try:
        import tiktoken

        return tiktoken.encoding_for_model(model)
    except Exception:
        return None


class TokenCounter:
    """Token 计数器. 按 settings.llm_model 取编码, 失败回退字符/4."""

    def __init__(self, model: str | None = None, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = model or self._settings.llm_model
        self._encoding = _load_encoding(self._model)

    def count(self, text: str) -> int:
        """统计文本 token 数; 空文本返回 0."""
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return len(text) // 4

    def exceeds(self, text: str, limit: int) -> bool:
        """文本 token 数是否超过上限."""
        return self.count(text) > limit
