"""上下文管理器单测 - 窗口/摘要/卸载/截断策略组合与 messages 组装."""

from knowflow.context.budget import BudgetManager
from knowflow.context.spiller import Spiller
from knowflow.context.strategy import ContextManager, ContextStrategy
from knowflow.context.summarizer import Summarizer
from knowflow.context.token_counter import TokenCounter
from knowflow.context.window import MessageWindow
from knowflow.core.config import Settings
from knowflow.sandbox.workspace import WorkspaceManager
from tests.fakes import FakeChatLLM, FakeMinio

# 小预算便于触发策略: 未知模型字符回退 token≈字符/4
_SETTINGS = Settings(
    llm_model="__unknown_model__",
    context_budget_tokens=800,
    window_max_turns=2,
    spill_threshold_tokens=50,
)


def _history(turns: int) -> list[dict]:
    return [
        msg
        for i in range(1, turns + 1)
        for msg in (
            {"role": "user", "content": f"第{i}轮问题内容" * 6},
            {"role": "assistant", "content": f"第{i}轮回答内容" * 6},
        )
    ]


def _manager(llm: FakeChatLLM | None = None, settings: Settings = _SETTINGS) -> ContextManager:
    ws = WorkspaceManager(FakeMinio())
    counter = TokenCounter(settings=settings)
    strategy = ContextStrategy(
        settings=settings,
        budget=BudgetManager(settings),
        window=MessageWindow(settings=settings),
        summarizer=Summarizer(llm) if llm is not None else None,
        spiller=Spiller(ws, settings=settings, counter=counter),
        counter=counter,
    )
    return ContextManager(settings=settings, strategy=strategy)


async def test_build_injects_retrieval_and_memory() -> None:
    """检索/记忆段落注入系统提示, 历史窗口截断."""
    result = await _manager().build(
        "当前问题",
        _history(5),
        session_id="1",
        retrieval="[1] 报销流程片段",
        memory="- 用户偏好简洁回答",
    )
    system = result.messages[0]["content"]
    assert "检索上下文" in system
    assert "[1] 报销流程片段" in system
    assert "用户记忆" in system
    assert "- 用户偏好简洁回答" in system
    # 窗口截断: 保留最近 2 轮 = 4 条消息 + system + user = 6 条
    assert len(result.messages) == 6
    assert result.messages[-1] == {"role": "user", "content": "当前问题"}
    assert "window" in result.stats.actions


async def test_history_summarized_when_over_budget() -> None:
    """历史超预算时 LLM 摘要替代, history 置空."""
    # 大窗口保留全部 20 轮, 历史 token 超 history 配额(280)触发摘要
    settings = Settings(
        llm_model="__unknown_model__",
        context_budget_tokens=800,
        window_max_turns=30,
        spill_threshold_tokens=50,
    )
    llm = FakeChatLLM(answer="摘要: 用户问过报销与年假。")
    result = await _manager(llm, settings=settings).build("新问题", _history(20), session_id="1")

    assert "summary" in result.stats.actions
    assert "摘要: 用户问过报销与年假。" in result.messages[0]["content"]
    # history 被摘要替代后只剩 system + user
    assert [m["role"] for m in result.messages] == ["system", "user"]


async def test_long_text_spilled_to_sandbox() -> None:
    """超阈值检索文本卸载到沙盒, 上下文注入引用."""
    long_retrieval = "长文本" * 100  # 300 字符 → 75 token > 50
    result = await _manager().build("问题", _history(1), session_id="42", retrieval=long_retrieval)

    assert "spill:retrieval" in result.stats.actions
    assert '"spilled": true' in result.messages[0]["content"]
    assert "/workspace/spilled/" in result.messages[0]["content"]


async def test_memory_truncated_when_over_budget() -> None:
    """记忆超预算时截断保留前缀."""
    long_memory = "用户偏好" * 200  # 800 字符 → 200 token > memory 配额(80)
    result = await _manager().build("问题", _history(1), session_id="1", memory=long_memory)

    assert "truncate:memory" in result.stats.actions
    assert long_memory[:64] in result.messages[0]["content"]
