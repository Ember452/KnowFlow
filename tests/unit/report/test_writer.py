"""章节撰写器单测 - 引用规范注入/失败降级."""

import pytest

from knowflow.agents.report.models import Evidence, EvidenceSource
from knowflow.agents.report.writer import Writer


class _FakeLLM:
    def __init__(self, response: str = "章节正文", raise_error: bool = False) -> None:
        self._response = response
        self._raise_error = raise_error
        self.last_messages: list[dict[str, str]] = []

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        self.last_messages = list(messages)
        if self._raise_error:
            raise RuntimeError("llm down")
        return self._response


def _evidence(n: int = 2) -> list[Evidence]:
    return [
        Evidence(source=EvidenceSource.KNOWLEDGE, content=f"证据内容{i}", title=f"文档{i}")
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_write_chapter_returns_body() -> None:
    """正常路径返回 LLM 生成的正文."""
    llm = _FakeLLM("生成的章节正文 [1]。")
    body = await Writer(llm=llm).write_chapter("标题", _evidence(), base_index=1)
    assert body == "生成的章节正文 [1]。"


@pytest.mark.asyncio
async def test_write_chapter_injects_citation_indexes() -> None:
    """prompt 注入证据全局下标(引用规范)."""
    llm = _FakeLLM()
    await Writer(llm=llm).write_chapter("标题", _evidence(3), base_index=5)
    user = llm.last_messages[-1]["content"]
    assert "[5] [knowledge] 文档0: 证据内容0" in user
    assert "[7] [knowledge] 文档2: 证据内容2" in user
    assert "只允许引用" in llm.last_messages[0]["content"]


@pytest.mark.asyncio
async def test_write_chapter_with_issues_requests_fix() -> None:
    """重写路径: 问题清单注入 prompt 要求逐条修正."""
    llm = _FakeLLM()
    await Writer(llm=llm).write_chapter(
        "标题", _evidence(1), base_index=1, issues=["引用 [9] 越界"]
    )
    user = llm.last_messages[-1]["content"]
    assert "上次审查未通过的问题" in user
    assert "引用 [9] 越界" in user


@pytest.mark.asyncio
async def test_write_chapter_llm_error_returns_empty() -> None:
    """LLM 异常返回空串(由流水线/规则校验降级)."""
    llm = _FakeLLM(raise_error=True)
    body = await Writer(llm=llm).write_chapter("标题", _evidence())
    assert body == ""
