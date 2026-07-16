"""QueryRewriter 单测 - 无历史不改写 / 改写成功 / 失败与空输出回退."""

import pytest

from knowflow.retrieval.query_rewriter import QueryRewriter


class _AIMessage:
    """模拟 langchain AIMessage(content 属性)."""

    def __init__(self, content: str) -> None:
        self.content = content


class _ScriptedLLM:
    """fake LLM: 按脚本返回响应; raise_on_call 时抛异常."""

    def __init__(self, responses: list[str] | None = None, raise_on_call: bool = False) -> None:
        self.responses = list(responses or [])
        self._idx = 0
        self.raise_on_call = raise_on_call
        self.calls: list[list[dict[str, str]]] = []

    async def ainvoke(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.raise_on_call:
            raise RuntimeError("llm down")
        resp = self.responses[self._idx] if self._idx < len(self.responses) else ""
        self._idx += 1
        return resp


@pytest.mark.asyncio
async def test_rewrite_without_history_skips_llm() -> None:
    """单轮(无历史)直接返回原 query, 不调用 LLM."""
    llm = _ScriptedLLM(responses=["改写结果"])
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite("报销流程", [])

    assert result == "报销流程"
    assert llm.calls == []


@pytest.mark.asyncio
async def test_rewrite_with_history_returns_rewritten() -> None:
    """有历史时返回 LLM 改写结果, 且携带历史与当前问题."""
    llm = _ScriptedLLM(responses=["报销流程的具体步骤"])
    rewriter = QueryRewriter(llm)
    history = [{"role": "user", "content": "报销流程是什么?"}]

    result = await rewriter.rewrite("它支持哪些步骤", history)

    assert result == "报销流程的具体步骤"
    assert len(llm.calls) == 1
    messages = llm.calls[0]
    assert messages[0]["role"] == "system"
    assert "报销流程是什么?" in messages[1]["content"]
    assert "它支持哪些步骤" in messages[1]["content"]


@pytest.mark.asyncio
async def test_rewrite_llm_failure_falls_back() -> None:
    """LLM 调用异常时回退原 query, 不抛出."""
    llm = _ScriptedLLM(raise_on_call=True)
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite("第二问", [{"role": "user", "content": "第一问"}])

    assert result == "第二问"


@pytest.mark.asyncio
async def test_rewrite_empty_output_falls_back() -> None:
    """LLM 输出为空时回退原 query."""
    llm = _ScriptedLLM(responses=["   "])
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite("第二问", [{"role": "user", "content": "第一问"}])

    assert result == "第二问"


@pytest.mark.asyncio
async def test_rewrite_repeat_output_falls_back() -> None:
    """LLM 复读原 query 时回退原 query."""
    llm = _ScriptedLLM(responses=["第二问"])
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite("第二问", [{"role": "user", "content": "第一问"}])

    assert result == "第二问"


@pytest.mark.asyncio
async def test_rewrite_extracts_aimessage_content() -> None:
    """langchain AIMessage 形态响应时提取 content 字段."""

    class _MsgLLM:
        async def ainvoke(self, messages: list[dict[str, str]]) -> _AIMessage:  # type: ignore[no-untyped-def]
            return _AIMessage(content="改写后的查询")

    rewriter = QueryRewriter(_MsgLLM())

    result = await rewriter.rewrite("它呢", [{"role": "user", "content": "第一问"}])

    assert result == "改写后的查询"


@pytest.mark.asyncio
async def test_rewrite_truncates_overlong_output() -> None:
    """超长改写结果截断到 500 字符."""
    long_text = "长" * 600
    llm = _ScriptedLLM(responses=[long_text])
    rewriter = QueryRewriter(llm)

    result = await rewriter.rewrite("第二问", [{"role": "user", "content": "第一问"}])

    assert len(result) == 500
