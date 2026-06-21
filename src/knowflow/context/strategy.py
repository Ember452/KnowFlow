"""上下文策略 - 超预算处理编排: 窗口 → 摘要 → 卸载 → 截断.

对历史/工具/检索/记忆各模块按预算检查, 超限时依次处理:
1. 历史: 滑动窗口裁剪 → 仍超预算则 LLM 摘要替代(摘要入系统提示)
2. 长文本(工具/检索): 沙盒卸载(spiller), 引用替换
3. 仍超限: 截断保留前缀并标记 truncated

处理记录进 ContextStats.actions, 供 trace/可观测展示.
"""

from dataclasses import dataclass, field

from knowflow.context.budget import BudgetManager
from knowflow.context.builder import ContextBuilder
from knowflow.context.spiller import Spiller
from knowflow.context.summarizer import Summarizer
from knowflow.context.token_counter import TokenCounter
from knowflow.context.window import MessageWindow
from knowflow.core.config import Settings, get_settings


@dataclass
class ContextStats:
    """上下文处理统计: 各模块 token 与执行过的动作."""

    tokens: dict[str, int] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)


@dataclass
class ProcessedContext:
    """策略处理后的上下文组件(供 builder 组装)."""

    history: list[dict]
    system_extra: str | None = None
    retrieval: str | None = None
    memory: str | None = None
    tools: str | None = None
    stats: ContextStats = field(default_factory=ContextStats)


class ContextStrategy:
    """上下文处理策略: 对输入组件按预算执行窗口/摘要/卸载/截断."""

    def __init__(
        self,
        settings: Settings | None = None,
        budget: BudgetManager | None = None,
        window: MessageWindow | None = None,
        summarizer: Summarizer | None = None,
        spiller: Spiller | None = None,
        counter: TokenCounter | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._budget = budget or BudgetManager(self._settings)
        self._window = window or MessageWindow(settings=self._settings)
        self._summarizer = summarizer
        self._spiller = spiller
        self._counter = counter or TokenCounter(settings=self._settings)

    async def process(
        self,
        *,
        history: list[dict],
        retrieval: str | None = None,
        memory: str | None = None,
        tools: str | None = None,
        session_id: int | str | None = None,
    ) -> ProcessedContext:
        """按策略处理各模块内容.

        Args:
            history: 原始历史消息(按轮).
            retrieval: 检索上下文文本.
            memory: 记忆召回文本.
            tools: 工具结果文本.
            session_id: 会话 id(卸载沙盒需要).

        Returns:
            ProcessedContext: 处理后的组件与统计.
        """
        stats = ContextStats()

        # 1. 历史: 窗口裁剪 → 超预算则摘要替代
        history = self._window.trim(history)
        stats.actions.append("window")
        history_tokens = self._counter.count(_concat(history))
        system_extra: str | None = None
        quota_history = self._budget.quota("history")
        if history_tokens > quota_history and self._summarizer is not None:
            summary = await self._summarizer.summarize(history)
            if summary:
                system_extra = f"历史摘要:\n{summary}"
                history = []
                stats.actions.append("summary")
                history_tokens = 0

        # 2. 长文本(检索/工具): 超阈值卸载到沙盒, 引用替换
        retrieval, tools = await self._process_texts(retrieval, tools, session_id, stats)

        # 3. 记忆: 超预算截断
        memory = self._truncate(memory, "memory", stats)

        stats.tokens = {
            "history": history_tokens,
            "retrieval": self._counter.count(retrieval or ""),
            "memory": self._counter.count(memory or ""),
            "tools": self._counter.count(tools or ""),
            "system_extra": self._counter.count(system_extra or ""),
        }
        return ProcessedContext(
            history=history,
            system_extra=system_extra,
            retrieval=retrieval,
            memory=memory,
            tools=tools,
            stats=stats,
        )

    async def _process_texts(
        self,
        retrieval: str | None,
        tools: str | None,
        session_id: int | str | None,
        stats: ContextStats,
    ) -> tuple[str | None, str | None]:
        """检索/工具长文本: 优先沙盒卸载, 未卸载且超预算时截断前缀."""
        if self._spiller is not None and session_id is not None:
            if retrieval:
                res = await self._spiller.spill_if_needed(retrieval, session_id)
                if res.spilled:
                    stats.actions.append("spill:retrieval")
                    retrieval = res.reference()
            if tools:
                res = await self._spiller.spill_if_needed(tools, session_id)
                if res.spilled:
                    stats.actions.append("spill:tools")
                    tools = res.reference()
        retrieval = self._truncate(retrieval, "retrieval", stats)
        tools = self._truncate(tools, "tools", stats)
        return retrieval, tools

    def _truncate(self, text: str | None, module: str, stats: ContextStats) -> str | None:
        """模块文本超预算时截断保留前缀并标记."""
        if not text:
            return text
        limit = self._budget.quota(module)
        if self._counter.exceeds(text, limit):
            stats.actions.append(f"truncate:{module}")
            # 按字符/4 近似截到预算内, 保留前缀
            chars = max(limit * 4, 64)
            return text[:chars]
        return text


def _concat(history: list[dict]) -> str:
    """历史消息拼成单串(供 token 统计)."""
    return "\n".join(f"{m.get('role', '')}: {m.get('content', '')}" for m in history)


@dataclass
class ContextResult:
    """上下文构建结果: 可直接注入 LLM 的 messages + 处理统计."""

    messages: list[dict[str, str]]
    stats: ContextStats


class ContextManager:
    """上下文管理器门面: 策略处理 + 组装, 对外输出 messages 与统计."""

    def __init__(
        self,
        settings: Settings | None = None,
        strategy: ContextStrategy | None = None,
        builder: ContextBuilder | None = None,
        budget: BudgetManager | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._strategy = strategy or ContextStrategy(settings=self._settings)
        self._builder = builder or ContextBuilder(self._settings)
        self._budget = budget or BudgetManager(self._settings)

    async def build(
        self,
        query: str,
        history: list[dict],
        *,
        session_id: int | str | None = None,
        retrieval: str | None = None,
        memory: str | None = None,
        tools: str | None = None,
    ) -> ContextResult:
        """完整上下文构建: 策略处理 → 组装 messages.

        Returns:
            ContextResult: messages 可直接注入 LLM, stats 供 trace.
        """
        processed = await self._strategy.process(
            history=history,
            retrieval=retrieval,
            memory=memory,
            tools=tools,
            session_id=session_id,
        )
        messages = self._builder.build(
            query,
            processed.history,
            system_extra=processed.system_extra,
            retrieval=processed.retrieval,
            memory=processed.memory,
            tools=processed.tools,
            max_history_tokens=self._budget.quota("history"),
        )
        return ContextResult(messages=messages, stats=processed.stats)
