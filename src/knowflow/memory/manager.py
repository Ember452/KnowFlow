"""记忆管理器 - 观察/沉淀/召回编排.

- observe(session_id, role, content): 消息写入短期记忆(Redis, TTL).
- sediment(session_id, user_id): 会话结束/每 N 轮触发, 筛选短期记忆中
  重要性 ≥ 阈值的消息, 压缩后写入长期记忆, 并清空短期.
- recall(query, user_id): 委托长期记忆召回, 结果注入对话系统提示.

should_sediment(turn_count) 为纯函数, 便于测试与上层调用.
"""

from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.memory.compressor import Compressor
from knowflow.memory.importance import ImportanceScorer
from knowflow.memory.long_term import LongTermMemoryManager
from knowflow.memory.short_term import ShortTermMemory

logger = get_logger(__name__)

_SEDIMENT_MAX_MSGS = 100  # 单次沉淀最多扫描的短期消息数


class MemoryManager:
    """记忆编排: 短期观察 → 重要性筛选 → 压缩 → 长期沉淀 → 召回."""

    def __init__(
        self,
        short_term: ShortTermMemory,
        importance: ImportanceScorer,
        compressor: Compressor,
        long_term: LongTermMemoryManager,
        settings: Settings | None = None,
    ) -> None:
        self._short_term = short_term
        self._importance = importance
        self._compressor = compressor
        self._long_term = long_term
        self._settings = settings or get_settings()

    @property
    def threshold(self) -> float:
        return self._settings.memory_sediment_threshold

    @property
    def interval(self) -> int:
        return self._settings.memory_sediment_interval

    @staticmethod
    def should_sediment(turn_count: int, interval: int = 5) -> bool:
        """是否达到沉淀时机: 每 interval 轮触发一次."""
        return turn_count > 0 and turn_count % interval == 0

    async def observe(self, session_id: int | str, role: str, content: str) -> None:
        """记录一条消息到短期记忆."""
        if not content:
            return
        await self._short_term.add(session_id, role, content)

    async def sediment(self, session_id: int | str, user_id: str) -> int:
        """沉淀短期记忆入长期: 筛选高重要性消息 → 压缩 → 入库 → 清空短期.

        Args:
            session_id: 会话 id.
            user_id: 用户标识(长期记忆按用户隔离).

        Returns:
            沉淀的长期记忆条数.
        """
        messages = await self._short_term.get_recent(session_id, n=_SEDIMENT_MAX_MSGS)
        if not messages:
            return 0
        # 只筛选用户消息(偏好/习惯通常由用户表达), 重要性 ≥ 阈值
        important: list[tuple[str, float]] = []
        for m in messages:
            if m.get("role") != "user":
                continue
            content = m.get("content", "")
            score = await self._importance.score(content)
            if score >= self.threshold:
                important.append((content, score))
        if important:
            summary = await self._compressor.compress([c for c, _ in important])
            for content, score in important:
                await self._long_term.save(
                    user_id=user_id,
                    session_id=int(session_id),
                    content=content,
                    importance=score,
                    summary=summary,
                )
            logger.info(
                "memory.sedimented",
                session_id=str(session_id),
                user_id=user_id,
                count=len(important),
            )
        # 无论是否沉淀, 短期记忆已消费, 清空避免重复
        await self._short_term.clear(session_id)
        return len(important)

    async def recall(self, query: str, user_id: str, top_k: int | None = None) -> list[Any]:
        """召回用户长期记忆(供对话系统提示注入)."""
        if not user_id:
            return []
        return await self._long_term.recall(query, user_id, top_k=top_k)

    async def list_by_user(self, user_id: str) -> list[Any]:
        """列出用户全部长期记忆(供 API 查询)."""
        return await self._long_term.list_by_user(user_id)

    async def delete(self, memory_id: int) -> bool:
        """删除一条长期记忆(供 API)."""
        return await self._long_term.delete(memory_id)

    def recall_text(self, hits: list[Any]) -> str:
        """召回结果格式化为系统提示文本."""
        if not hits:
            return ""
        return "\n".join(f"- {h.content}" for h in hits)
