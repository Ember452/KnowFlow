"""记忆管理器 - 观察/沉淀/召回编排 + 治理(蒸馏/冲突/可观测).

- observe(session_id, role, content): 消息写入短期记忆(Redis, TTL).
- sediment(session_id, user_id): 会话结束/每 N 轮触发, 筛选短期记忆中
  重要性 ≥ 阈值的消息, 压缩后写入长期记忆 + 蒸馏为会话摘要, 并清空短期.
- recall(query, user_id): 委托长期记忆召回(含核心记忆摘要), 结果注入对话
  系统提示; 经可选 tracer 记录召回 span(命中记忆 id + 置信度).

治理能力:
- 蒸馏: sediment 时压缩结果写入 memory_summaries(核心记忆), recall 时注入
- 冲突: sediment 时对新记忆做冲突检测, 发现矛盾写入 memory_conflicts 留痕
- 可观测: recall 命中明细经 tracer span 记录(命中 id/相似度), 无 tracer 时
  仅结构化日志

should_sediment(turn_count) 为纯函数, 便于测试与上层调用.
"""

from typing import Any

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.memory.compressor import Compressor
from knowflow.memory.conflict import ConflictDetector, ConflictStore
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
        conflict_detector: ConflictDetector | None = None,
        conflict_store: ConflictStore | None = None,
        tracer: Any | None = None,
    ) -> None:
        """初始化.

        Args:
            short_term: 短期记忆(Redis).
            importance: 重要性评分器.
            compressor: 记忆压缩器(蒸馏用).
            long_term: 长期记忆管理器(PG + 向量).
            settings: Settings 单例.
            conflict_detector: 冲突检测器; None 时用默认启发式实现.
            conflict_store: 冲突记录存储; None 时冲突仅日志告警不落库.
            tracer: 可选 Tracer(实现 start_span/end_span), 记录召回 span.
        """
        self._short_term = short_term
        self._importance = importance
        self._compressor = compressor
        self._long_term = long_term
        self._settings = settings or get_settings()
        self._conflict_detector = conflict_detector or ConflictDetector()
        self._conflict_store = conflict_store
        self._tracer = tracer

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
                # 冲突检测: 与存量记忆矛盾时留痕(新记忆照常生效, 不阻断写入)
                await self._track_conflicts(user_id, content)
                await self._long_term.save(
                    user_id=user_id,
                    session_id=int(session_id),
                    content=content,
                    importance=score,
                    summary=summary,
                )
            # 蒸馏: 压缩摘要沉淀为会话级核心记忆(recall 时注入)
            if summary:
                await self._long_term.save_summary(user_id, int(session_id), summary)
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
        """召回用户长期记忆(供对话系统提示注入).

        经可选 tracer 记录 memory_recall span(命中记忆 id + 相似度),
        无 tracer 时仅记录结构化日志(可观测不阻塞主流程).
        """
        if not user_id:
            return []
        hits = await self._long_term.recall(query, user_id, top_k=top_k)
        await self._record_recall_observability(query, user_id, hits)
        return hits

    async def latest_summary(self, user_id: str) -> str | None:
        """取用户核心记忆摘要(蒸馏产物), 供调用方注入系统提示."""
        if not user_id:
            return None
        return await self._long_term.latest_summary(user_id)

    async def _record_recall_observability(self, query: str, user_id: str, hits: list[Any]) -> None:
        """记忆召回可观测: tracer span + 结构化日志记录命中明细."""
        detail = [
            {"memory_id": getattr(h, "memory_id", None), "score": getattr(h, "score", None)}
            for h in hits
        ]
        logger.info(
            "memory.recalled", user_id=user_id, query=query[:80], hits=len(hits), detail=detail
        )
        if self._tracer is None or not hits:
            return
        tracer = self._tracer
        try:
            span = await tracer.start_span(
                "memory_recall",
                "memory.recall",
                input={"query": query[:200], "user_id": user_id},
            )
            await tracer.end_span(span, output={"hits": detail, "count": len(hits)})
        except Exception as exc:
            # 可观测失败不阻塞记忆召回
            logger.warning("memory.trace_failed", error=str(exc))

    async def _track_conflicts(self, user_id: str, content: str) -> None:
        """新记忆与存量记忆冲突检测: 有冲突时写入留痕或仅日志告警."""
        existing = await self._long_term.list_by_user(user_id)
        if not existing:
            return
        findings = self._conflict_detector.detect(content, existing)
        for finding in findings:
            if self._conflict_store is not None:
                await self._conflict_store.record(finding, user_id=user_id, new_content=content)
            logger.warning(
                "memory.conflict_detected",
                user_id=user_id,
                new_content=content[:80],
                old_memory_id=finding.old_memory_id,
                reason=finding.reason,
            )

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
