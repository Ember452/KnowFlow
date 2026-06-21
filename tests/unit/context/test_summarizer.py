"""历史摘要单测 - LLM 摘要/增量 compact/失败兜底."""

from knowflow.context.summarizer import Summarizer
from tests.fakes import FakeChatLLM


def _history(turns: int = 2) -> list[dict[str, str]]:
    return [
        msg
        for i in range(1, turns + 1)
        for msg in (
            {"role": "user", "content": f"第{i}轮问题"},
            {"role": "assistant", "content": f"第{i}轮回答"},
        )
    ]


async def test_summarize_uses_llm() -> None:
    """LLM 返回摘要文本."""
    llm = FakeChatLLM(answer="用户询问报销流程。")
    result = await Summarizer(llm).summarize(_history())
    assert result == "用户询问报销流程。"
    # 消息序列: system + user
    assert llm.last_messages[0]["role"] == "system"
    assert "第1轮问题" in llm.last_messages[1]["content"]


async def test_summarize_incremental_with_previous() -> None:
    """增量 compact: 旧摘要 + 新消息一起发给 LLM."""
    llm = FakeChatLLM(answer="更新摘要")
    await Summarizer(llm).summarize(_history(), previous_summary="旧摘要内容")
    assert "旧摘要内容" in llm.last_messages[1]["content"]


async def test_summarize_empty_returns_previous() -> None:
    llm = FakeChatLLM()
    assert await Summarizer(llm).summarize([], previous_summary="旧摘要") == "旧摘要"
    assert await Summarizer(llm).summarize([]) == ""


async def test_summarize_fallback_on_llm_failure() -> None:
    """LLM 抛异常时回退规则抽取, 不中断流程."""

    class _BoomLLM:
        async def ainvoke(self, messages):  # type: ignore[no-untyped-def]
            raise RuntimeError("llm down")

    result = await Summarizer(_BoomLLM()).summarize(_history())
    assert "第1轮问题" in result
    assert "第2轮回答" in result


async def test_summarize_fallback_on_empty_answer() -> None:
    """LLM 返回空文本时回退规则抽取."""
    llm = FakeChatLLM(answer="")
    result = await Summarizer(llm).summarize(_history())
    assert "第1轮问题" in result
