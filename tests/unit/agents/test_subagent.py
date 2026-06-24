"""Subagent / AgentRegistry 单测."""

from typing import Any, ClassVar

import pytest

from knowflow.agents.registry import AgentRegistry
from knowflow.agents.subagent import Subagent


class FakeLLM:
    """记录消息并返回固定文本."""

    def __init__(self, answer: str = "子任务结果") -> None:
        self.answer = answer
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages: list[object]) -> str:
        self.calls.append(list(messages))
        return self.answer


# ── Subagent ──


@pytest.mark.asyncio
async def test_subagent_execute_isolated_context() -> None:
    """execute 组装独立上下文: system(含检索上下文) + 子任务."""
    llm = FakeLLM("A 的价格是 100")
    sub = Subagent(llm=llm)
    result = await sub.execute("查 A 的价格", retrieval_context="A 售价 100 元")
    assert result["output"] == "A 的价格是 100"
    messages = llm.calls[0]
    assert messages[0]["role"] == "system"
    assert "A 售价 100 元" in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "查 A 的价格"}


@pytest.mark.asyncio
async def test_subagent_execute_without_context() -> None:
    """无检索上下文时 system 不含上下文块."""
    llm = FakeLLM("结果")
    sub = Subagent(llm=llm)
    await sub.execute("任务", retrieval_context="")
    system = llm.calls[0][0]["content"]
    assert "检索上下文:\n" not in system  # 上下文块整体不出现


@pytest.mark.asyncio
async def test_subagent_uses_context_manager() -> None:
    """注入独立 ContextManager 时优先走上下文策略组装."""

    class FakeContextManager:
        async def build(
            self, query: str, history: list, session_id: int | None, retrieval: str | None
        ) -> Any:
            class Ctx:
                messages: ClassVar[list[dict[str, str]]] = [
                    {"role": "system", "content": "策略上下文"},
                    {"role": "user", "content": query},
                ]

            return Ctx()

    llm = FakeLLM("策略结果")
    sub = Subagent(llm=llm, context_manager=FakeContextManager())
    result = await sub.execute("任务", retrieval_context="ctx", session_id=7)
    assert result["output"] == "策略结果"
    assert llm.calls[0][0]["content"] == "策略上下文"


@pytest.mark.asyncio
async def test_subagent_three_step_loop() -> None:
    """decide/act/observe 三步循环输出结果."""
    llm = FakeLLM("输出")
    sub = Subagent(llm=llm)
    state = {"task": "查 A", "retrieval_context": "", "session_id": 1}
    assert (await sub.decide(state)) == {"action": "execute"}
    acted = await sub.act(state)
    assert acted["output"] == "输出"
    assert (await sub.observe(acted)) == {"output": "输出"}


# ── AgentRegistry ──


def test_registry_register_and_query() -> None:
    registry = AgentRegistry()
    sub = Subagent()
    registry.register(sub)
    assert registry.get("sub") is sub
    assert registry.names() == ["sub"]
    assert registry.get("main") is None


def test_registry_overwrite_warns() -> None:
    registry = AgentRegistry()
    registry.register(Subagent())
    registry.register(Subagent())  # 同名覆盖不抛异常
    assert len(registry.list_all()) == 1
