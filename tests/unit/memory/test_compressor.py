"""记忆压缩单测 - LLM 压缩与失败兜底."""

from knowflow.memory.compressor import Compressor
from tests.fakes import FakeChatLLM


async def test_compress_uses_llm() -> None:
    """LLM 返回压缩摘要."""
    llm = FakeChatLLM(answer="偏好: Markdown 文档; 部门: 财务")
    result = await Compressor(llm).compress(["我喜欢 Markdown", "我是财务部的"])
    assert result == "偏好: Markdown 文档; 部门: 财务"
    assert "我喜欢 Markdown" in llm.last_messages[1]["content"]


async def test_compress_empty_returns_empty() -> None:
    assert await Compressor().compress([]) == ""


async def test_compress_fallback_on_llm_failure() -> None:
    """LLM 失败时回退规则拼接, 不中断流程."""

    class _BoomLLM:
        async def ainvoke(self, messages):  # type: ignore[no-untyped-def]
            raise RuntimeError("llm down")

    result = await Compressor(_BoomLLM()).compress(["记忆A", "记忆B"])
    assert "记忆A" in result
    assert "记忆B" in result


async def test_compress_without_llm() -> None:
    """无 LLM 时直接规则拼接."""
    result = await Compressor().compress(["记忆A", "记忆B"])
    assert result == "记忆A; 记忆B"


async def test_compress_caps_items() -> None:
    """超过上限时只压缩前 N 条."""
    many = [f"记忆{i}" for i in range(30)]
    result = await Compressor().compress(many)
    assert "记忆0" in result
    assert "记忆19" in result
    assert "记忆29" not in result
