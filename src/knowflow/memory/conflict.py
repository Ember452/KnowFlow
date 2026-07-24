"""记忆冲突检测与留痕 - 新记忆与存量记忆语义矛盾时生成冲突记录.

检测为启发式规则(无 LLM 依赖, 可复现可单测):
- 主题重叠(文本相似度 >= 阈值) + 否定极性相反 → 方向冲突
  (如 "喜欢 X" vs "不喜欢 X")
- 主题重叠 + 数值不一致(两段各含数字且数字集合不同) → 数值冲突
  (如 "预算 100" vs "预算 200")

规则不完美但覆盖最常见矛盾形态; 检测结果仅留痕(新记忆照常生效),
供人工审查/后续仲裁, 不阻断记忆写入.
"""

from dataclasses import dataclass
from difflib import SequenceMatcher
from re import findall

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.logging import get_logger
from knowflow.models.memory import LongTermMemory, MemoryConflict

logger = get_logger(__name__)

# 主题重叠相似度阈值(低于该值视为不同主题, 不判冲突)
_SIMILARITY_THRESHOLD = 0.3
# 否定/方向反转词: 出现即视为该条记忆表达"反对/不喜欢"倾向
_NEGATION_WORDS = ("不", "别", "讨厌", "拒绝", "禁止", "反对", "不喜欢", "不推荐")
# 数值冲突判定: 两段数值集合完全不同才判冲突(避免 "提到 3 个方案" 误伤)
_NUMBER_RE = r"\d+(?:\.\d+)?"


@dataclass(frozen=True)
class ConflictFinding:
    """单条冲突发现."""

    old_memory_id: int
    old_content: str
    reason: str


class ConflictDetector:
    """启发式记忆冲突检测器(纯函数式, 无状态)."""

    def detect(self, new_content: str, memories: list[LongTermMemory]) -> list[ConflictFinding]:
        """检测新记忆与存量记忆的冲突, 返回发现列表(按相似度降序)."""
        new_text = new_content.strip()
        if not new_text:
            return []
        findings: list[ConflictFinding] = []
        for mem in memories:
            old_text = (mem.content or "").strip()
            if not old_text:
                continue
            reason = self._conflict_reason(new_text, old_text)
            if reason:
                findings.append(
                    ConflictFinding(old_memory_id=int(mem.id), old_content=old_text, reason=reason)
                )
        # 相似度高的冲突排前面(更可能是同一主题的真实矛盾)
        findings.sort(
            key=lambda f: SequenceMatcher(None, new_text, f.old_content).ratio(), reverse=True
        )
        return findings

    @staticmethod
    def _conflict_reason(new_text: str, old_text: str) -> str | None:
        """判定两条记忆是否冲突, 返回冲突原因; 无冲突返回 None."""
        sim = SequenceMatcher(None, new_text, old_text).ratio()
        if sim < _SIMILARITY_THRESHOLD:
            return None
        new_neg = any(w in new_text for w in _NEGATION_WORDS)
        old_neg = any(w in old_text for w in _NEGATION_WORDS)
        if new_neg != old_neg:
            direction = "反对" if new_neg else "支持"
            return f"主题相似但态度反转({direction}旧记忆)"
        new_nums = set(findall(_NUMBER_RE, new_text))
        old_nums = set(findall(_NUMBER_RE, old_text))
        if new_nums and old_nums and new_nums != old_nums:
            return f"数值不一致(旧 {sorted(old_nums)} vs 新 {sorted(new_nums)})"
        return None


class ConflictStore:
    """冲突记录存储: 写 memory_conflicts 表留痕(供 API 查询/人工审查)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, finding: ConflictFinding, *, user_id: str, new_content: str) -> int:
        """写入一条冲突记录, 返回记录 id."""
        conflict = MemoryConflict(
            user_id=user_id,
            new_content=new_content,
            old_memory_id=finding.old_memory_id,
            old_content=finding.old_content,
            reason=finding.reason,
            status="pending",
        )
        self._session.add(conflict)
        await self._session.flush()
        return int(conflict.id)

    async def list_by_user(self, user_id: str) -> list[MemoryConflict]:
        """按用户列出冲突记录(最新在前)."""
        result = await self._session.execute(
            select(MemoryConflict)
            .where(MemoryConflict.user_id == user_id)
            .order_by(MemoryConflict.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_pending(self, user_id: str) -> list[MemoryConflict]:
        """列出待处理冲突."""
        result = await self._session.execute(
            select(MemoryConflict)
            .where(MemoryConflict.user_id == user_id, MemoryConflict.status == "pending")
            .order_by(MemoryConflict.created_at.desc())
        )
        return list(result.scalars().all())

    async def resolve(self, conflict_id: int) -> bool:
        """标记冲突已处理; 不存在返回 False."""
        conflict = await self._session.get(MemoryConflict, conflict_id)
        if conflict is None:
            return False
        conflict.status = "resolved"
        return True
