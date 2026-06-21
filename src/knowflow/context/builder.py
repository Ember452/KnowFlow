"""上下文组装器 - 将各模块内容按预算截断并组装为 LLM messages.

纯组装职责: 系统提示(含检索/记忆/工具段落) + 历史 + 当前问题.
各模块文本先按预算截断(超出时保留前缀并标记截断), 由策略层决定
哪些模块先经摘要/卸载处理.
"""

from knowflow.core.config import Settings, get_settings


class ContextBuilder:
    """上下文组装器. 按模块预算截断文本并构建 messages."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def build(
        self,
        query: str,
        history: list[dict],
        *,
        system_extra: str | None = None,
        retrieval: str | None = None,
        memory: str | None = None,
        tools: str | None = None,
        max_history_tokens: int | None = None,
    ) -> list[dict[str, str]]:
        """组装 messages: 系统提示(段落式) + 历史 + 当前问题.

        Args:
            query: 当前用户问题.
            history: 窗口截断后的历史消息列表.
            system_extra: 系统提示附加内容(如角色要求).
            retrieval: 检索上下文文本(带 [n] 标注).
            memory: 记忆召回文本.
            tools: 工具结果/说明文本.
            max_history_tokens: 历史最大 token 数, 超限截断(按字符近似).

        Returns:
            LLM messages 列表(role/content).
        """
        sections: list[str] = []
        if system_extra:
            sections.append(system_extra)
        if retrieval:
            sections.append("检索上下文:\n" + retrieval)
        if memory:
            sections.append("用户记忆:\n" + memory)
        if tools:
            sections.append("工具说明:\n" + tools)
        system = "你是 KnowFlow 企业知识库助手. " + ("\n\n".join(sections) if sections else "")
        history = self._truncate_history(history, max_history_tokens)
        return [{"role": "system", "content": system}, *history, {"role": "user", "content": query}]

    @staticmethod
    def _truncate_history(history: list[dict], max_tokens: int | None) -> list[dict]:
        """历史按 token 上限截断(字符/4 近似), 保留最近的轮次."""
        if max_tokens is None or max_tokens <= 0:
            return history
        total = 0
        kept: list[dict] = []
        for msg in reversed(history):
            tokens = len(msg.get("content", "")) // 4
            if total + tokens > max_tokens and kept:
                break
            total += tokens
            kept.append(msg)
        return list(reversed(kept))
