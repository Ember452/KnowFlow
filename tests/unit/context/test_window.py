"""滑动窗口单测 - 按轮截断与边界."""

from knowflow.context.window import MessageWindow, trim_history


def _history(turns: int) -> list[dict]:
    """构造 turns 轮历史(user+assistant 各一条)."""
    return [
        {"role": role, "content": f"第{i}轮{role}"}
        for i in range(1, turns + 1)
        for role in ("user", "assistant")
    ]


def test_trim_keeps_recent_turns() -> None:
    """保留最近 max_turns 轮(每轮 2 条)."""
    trimmed = trim_history(_history(10), max_turns=3)
    assert len(trimmed) == 6
    assert trimmed[0]["content"] == "第8轮user"
    assert trimmed[-1]["content"] == "第10轮assistant"


def test_trim_no_op_when_within_window() -> None:
    h = _history(3)
    assert trim_history(h, max_turns=5) == h


def test_trim_zero_or_negative_returns_empty() -> None:
    assert trim_history(_history(3), max_turns=0) == []
    assert trim_history(_history(3), max_turns=-1) == []


def test_message_window_uses_settings_default() -> None:
    from knowflow.core.config import Settings

    window = MessageWindow(max_turns=2)
    assert window.max_turns == 2
    assert len(window.trim(_history(5))) == 4
    # settings 默认值注入
    window2 = MessageWindow(settings=Settings(window_max_turns=1))
    assert len(window2.trim(_history(5))) == 2
