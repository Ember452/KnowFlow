"""Subagent / AgentRegistry 单测."""

from typing import Any, ClassVar

import pytest

from knowflow.agents.registry import AgentRegistry
from knowflow.agents.subagent import Subagent, quality_check
from knowflow.tools.domain import AgentRole
from tests.fakes import FakeToolOrchestrator


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


@pytest.mark.parametrize(
    "output,min_chars,expected_ok",
    [
        ("", 20, False),
        ("   \n ", 20, False),
        ("短", 20, False),
        ("这是一个足够长的有效输出内容可以正常通过质量门禁", 20, True),
        ("恰好", 2, True),
    ],
)
def test_quality_check(output: str, min_chars: int, expected_ok: bool) -> None:
    """质量门禁: 空/过短判定无效, 正常输出通过."""
    ok, reason = quality_check(output, min_chars=min_chars)
    assert ok is expected_ok
    if not expected_ok:
        assert reason  # 未通过时必须带原因


@pytest.mark.asyncio
async def test_subagent_execute_with_retry_hint() -> None:
    """retry_hint 追加为最后一条 user 消息(重试原因注入修正)."""
    llm = FakeLLM("重试后的结果")
    sub = Subagent(llm=llm)
    result = await sub.execute("查 A", retrieval_context="ctx", retry_hint="上次执行失败: 超时")
    assert result["output"] == "重试后的结果"
    messages = llm.calls[0]
    assert messages[-1] == {"role": "user", "content": "[上次执行反馈] 上次执行失败: 超时"}


@pytest.mark.asyncio
async def test_subagent_execute_without_hint_no_extra_message() -> None:
    """无 retry_hint 时不追加消息(消息结构不变)."""
    llm = FakeLLM("结果")
    sub = Subagent(llm=llm)
    await sub.execute("任务", retrieval_context="ctx")
    assert len(llm.calls[0]) == 2  # system + user 两条


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


# ── 子 Agent 工具化 ──


@pytest.mark.asyncio
async def test_subagent_tool_path_uses_orchestrator() -> None:
    """注入 tool_orchestrator 时走工具循环: SUBAGENT 角色 + 工具清单 prompt + tool_calls 返回."""
    from knowflow.services.tool_orchestrator import ToolCallRecord

    fake_orc = FakeToolOrchestrator(answer="计算完成, 结果已生成")
    fake_orc.tool_calls = [
        ToolCallRecord(
            tool_name="calculator",
            args={"expression": "2**10"},
            success=True,
            output=1024,
            latency_ms=1.0,
        )
    ]
    sub = Subagent(llm=FakeLLM(), tool_orchestrator=fake_orc)
    result = await sub.execute("计算 2 的 10 次方", retrieval_context="ctx", session_id=7)

    assert result["output"] == "计算完成, 结果已生成"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool_name"] == "calculator"
    # 编排器以 SUBAGENT 角色运行, system prompt 含工具清单与检索上下文
    call = fake_orc.run_calls[0]
    assert call["agent_role"] == AgentRole.SUBAGENT
    assert call["session_id"] == "7"
    assert call["system_prompt"] is not None
    assert "calculator" in call["system_prompt"]
    assert "检索上下文:\nctx" in call["system_prompt"]


@pytest.mark.asyncio
async def test_subagent_tool_path_retry_hint_in_task() -> None:
    """工具路径下 retry_hint 拼入任务描述(无独立消息通道)."""
    fake_orc = FakeToolOrchestrator(answer="修正后的有效输出内容")
    sub = Subagent(llm=FakeLLM(), tool_orchestrator=fake_orc)
    await sub.execute("查数据", retrieval_context="", retry_hint="上次执行失败: 超时")
    query = fake_orc.run_calls[0]["query"]
    assert "[上次执行反馈] 上次执行失败: 超时" in query


@pytest.mark.asyncio
async def test_subagent_tool_path_on_tool_callback() -> None:
    """工具路径下 on_tool 回调逐条上抛工具调用记录."""
    from knowflow.services.tool_orchestrator import ToolCallRecord

    fake_orc = FakeToolOrchestrator(answer="文件已写出, 内容完整")
    fake_orc.tool_calls = [
        ToolCallRecord(
            tool_name="file_write_tool", args={}, success=True, output="ok", latency_ms=2.0
        )
    ]
    sub = Subagent(llm=FakeLLM(), tool_orchestrator=fake_orc)
    received: list[object] = []

    async def _on_tool(record: object) -> None:
        received.append(record)

    await sub.execute("写文件", retrieval_context="", on_tool=_on_tool)
    assert len(received) == 1
    assert received[0].tool_name == "file_write_tool"  # type: ignore[attr-defined]


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
