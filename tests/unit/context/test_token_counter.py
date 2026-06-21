"""Token 计数单测 - 精确计数与字符回退."""

from knowflow.context.token_counter import TokenCounter
from knowflow.core.config import Settings


def test_count_with_fallback_when_model_unknown() -> None:
    """未知模型回退字符/4 估算."""
    settings = Settings(llm_model="__unknown_model__")
    counter = TokenCounter(settings=settings)
    assert counter.count("") == 0
    assert counter.count("hello world") == len("hello world") // 4


def test_count_with_known_model() -> None:
    """已知模型用 tiktoken 精确计数(deepseek-chat 映射到 cl100k_base)."""
    counter = TokenCounter(model="gpt-4o")
    assert counter.count("hello world") > 0


def test_exceeds_threshold() -> None:
    counter = TokenCounter(model="gpt-4o")
    assert counter.exceeds("x" * 1000, 10) is True
    assert counter.exceeds("x" * 5, 100) is False
