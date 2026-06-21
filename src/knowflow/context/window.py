"""滑动窗口 - 保留最近 N 轮对话历史, 超限截断.

每轮对话占 2 条消息(user + assistant); 窗口按轮数裁剪, 保证注入的
历史始终在最近 window_max_turns 轮内, 长会话不再无限膨胀.
"""

from knowflow.core.config import Settings, get_settings


def trim_history(history: list[dict], max_turns: int) -> list[dict]:
    """按轮截断历史: 每轮 2 条, 保留最近 max_turns 轮; max_turns<=0 返回空."""
    if max_turns <= 0:
        return []
    return history[-(max_turns * 2) :]


class MessageWindow:
    """会话消息滑动窗口. 按 settings.window_max_turns 轮截断."""

    def __init__(self, max_turns: int | None = None, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._max_turns = max_turns if max_turns is not None else self._settings.window_max_turns

    @property
    def max_turns(self) -> int:
        return self._max_turns

    def trim(self, history: list[dict]) -> list[dict]:
        """截断到最近 max_turns 轮."""
        return trim_history(history, self._max_turns)
