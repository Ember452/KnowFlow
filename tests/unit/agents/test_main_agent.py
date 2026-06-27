"""MainAgent 单测 - 意图分类/规划解析/汇总/三步循环."""

import pytest

from knowflow.agents.main_agent import MainAgent


class FakeLLM:
    """脚本化 fake LLM: 按序返回字符串响应, 记录消息."""

    def __init__(self, script: list[str]) -> None:
        self._script = list(script)
        self._idx = 0
        self.calls: list[list[object]] = []

    async def ainvoke(self, messages: list[object]) -> str:
        # 兼容 str(plan/summarize 直传)与 list(messages) 两种调用形态
        self.calls.append(messages if isinstance(messages, str) else list(messages))
        if self._idx < len(self._script):
            resp = self._script[self._idx]
            self._idx += 1
            return resp
        return "默认回复"


# ── understand 规则分类 ──


@pytest.mark.parametrize(
    "query,expected",
    [
        ("公司报销流程是什么?", "simple"),
        ("帮我算 2 的 10 次方", "simple"),
        ("对比 A 和 B 两款产品的价格", "complex"),
        ("分别查询三款产品的参数并汇总", "complex"),
        ("A/B/C 三个方案优缺点", "complex"),
        ("", "simple"),
    ],
)
def test_understand_classification(query: str, expected: str) -> None:
    """复杂信号词/多候选分隔符判 complex, 否则 simple."""
    assert MainAgent.understand(query) == expected


# ── plan 规划 ──


@pytest.mark.asyncio
async def test_plan_parses_delegation_json() -> None:
    """plan 解析 LLM JSON 输出(含代码块包裹)."""
    llm = FakeLLM(
        [
            '```json\n{"needs_delegation": true, "reason": "可拆分", '
            '"subtasks": [{"id": "t1", "task": "查 A", "description": "A"}, '
            '{"id": "t2", "task": "查 B", "description": "B"}]}\n```'
        ]
    )
    agent = MainAgent(llm=llm)
    plan = await agent.plan("对比 A 和 B")
    assert plan.needs_delegation is True
    assert [s["id"] for s in plan.subtasks] == ["t1", "t2"]
    assert plan.subtasks[0]["task"] == "查 A"


@pytest.mark.asyncio
async def test_plan_degrades_when_json_invalid() -> None:
    """JSON 解析失败重试后降级为不委派."""
    llm = FakeLLM(["不是 JSON", "还是不是 JSON", "依旧不是 JSON"])
    agent = MainAgent(llm=llm)
    plan = await agent.plan("对比 A 和 B")
    assert plan.needs_delegation is False
    assert "规划解析失败" in plan.reason
    assert llm.calls  # 至少调用过一次


@pytest.mark.asyncio
async def test_plan_rejects_delegation_with_single_subtask() -> None:
    """委派模式但子任务数不足 2 → 降级不委派."""
    llm = FakeLLM(
        [
            '{"needs_delegation": true, "subtasks": [{"id": "t1", "task": "查 A"}]}',
            '{"needs_delegation": true, "subtasks": [{"id": "t1", "task": "查 A"}]}',
            '{"needs_delegation": true, "subtasks": [{"id": "t1", "task": "查 A"}]}',
        ]
    )
    agent = MainAgent(llm=llm)
    plan = await agent.plan("对比 A 和 B")
    assert plan.needs_delegation is False


@pytest.mark.asyncio
async def test_plan_no_delegation() -> None:
    """LLM 判定无需委派."""
    llm = FakeLLM(['{"needs_delegation": false, "reason": "单一问答", "subtasks": []}'])
    agent = MainAgent(llm=llm)
    plan = await agent.plan("报销流程")
    assert plan.needs_delegation is False
    assert plan.subtasks == []


# ── summarize / direct_answer ──


@pytest.mark.asyncio
async def test_summarize_formats_results() -> None:
    """汇总 prompt 包含原始问题与子结果."""
    llm = FakeLLM(["汇总答案"])
    agent = MainAgent(llm=llm)
    answer = await agent.summarize(
        "对比 A 和 B",
        [
            {"subtask_id": "t1", "success": True, "output": "A 是 100"},
            {"subtask_id": "t2", "success": False, "error": "查不到 B"},
        ],
    )
    assert answer == "汇总答案"
    prompt = llm.calls[0]  # summarize 直传 str prompt
    assert isinstance(prompt, str)
    assert "对比 A 和 B" in prompt
    assert "A 是 100" in prompt
    assert "查不到 B" in prompt


@pytest.mark.asyncio
async def test_direct_answer_with_context() -> None:
    """直答注入检索上下文到 system prompt."""
    llm = FakeLLM(["直接答案"])
    agent = MainAgent(llm=llm)
    answer = await agent.direct_answer("报销流程", context="报销需填表")
    assert answer == "直接答案"
    system = llm.calls[0][0]["content"]
    assert "报销需填表" in system


@pytest.mark.asyncio
async def test_direct_answer_with_history() -> None:
    """直答注入最近对话历史(多轮省略语境可追溯)."""
    llm = FakeLLM(["直接答案"])
    agent = MainAgent(llm=llm)
    history = [
        {"role": "user", "content": "对比 A 和 B 的价格"},
        {"role": "assistant", "content": "A 100, B 200"},
    ]
    answer = await agent.direct_answer("那 C 呢", context="产品资料", history=history)
    assert answer == "直接答案"
    messages = llm.calls[0]
    # system + 历史 2 条 + 当前问题
    assert len(messages) == 4
    assert messages[1:3] == history
    assert messages[-1] == {"role": "user", "content": "那 C 呢"}


@pytest.mark.asyncio
async def test_plan_degrades_when_llm_raises() -> None:
    """LLM 调用抛异常(网络/限流)时重试后降级为不委派, 不阻塞对话."""

    class RaisingLLM:
        """每次调用都抛 RuntimeError 的 fake LLM."""

        async def ainvoke(self, prompt: object) -> str:
            raise RuntimeError("LLM API 连接失败")

    agent = MainAgent(llm=RaisingLLM())
    plan = await agent.plan("对比 A 和 B")
    assert plan.needs_delegation is False
    assert "规划解析失败" in plan.reason
    assert "LLM API 连接失败" in plan.reason


# ── decide/act/observe 三步循环 ──


@pytest.mark.asyncio
async def test_decide_act_observe_delegation_path() -> None:
    """三步循环: decide 判委派 → act 输出子任务 → observe 汇总."""
    llm = FakeLLM(
        [
            '{"needs_delegation": true, "reason": "可拆分", '
            '"subtasks": [{"id": "t1", "task": "查 A"}, {"id": "t2", "task": "查 B"}]}',
            "汇总答案",
        ]
    )
    agent = MainAgent(llm=llm)
    state = {"query": "对比 A 和 B"}
    decided = await agent.decide(state)
    assert decided["intent"] == "complex"
    assert decided["needs_delegation"] is True
    acted = await agent.act(state)
    assert len(acted["plan"]) == 2
    observed = await agent.observe(
        {**state, "subtask_results": [{"subtask_id": "t1", "success": True, "output": "x"}]}
    )
    assert observed["final_answer"] == "汇总答案"


@pytest.mark.asyncio
async def test_decide_simple_no_llm_plan() -> None:
    """simple 任务 decide 不调 LLM 规划, 直接不委派."""
    llm = FakeLLM([])
    agent = MainAgent(llm=llm)
    decided = await agent.decide({"query": "报销流程是什么?"})
    assert decided["needs_delegation"] is False
    assert decided["intent"] == "simple"
    assert llm.calls == []
