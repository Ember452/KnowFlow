"""记忆端点 - 长期记忆查询/删除/手动沉淀.

GET /memory/{user_id}         列出用户长期记忆
DELETE /memory/{user_id}/{id} 删除单条记忆
POST /memory/{user_id}/sediment 手动沉淀(会话短期记忆 → 长期, 含压缩)
"""

from typing import Any

from fastapi import APIRouter

from knowflow.api.deps import DbDep, EmbeddingDep, LlmDep, RedisDep
from knowflow.core.exceptions import NotFoundError
from knowflow.memory.compressor import Compressor
from knowflow.memory.importance import ImportanceScorer
from knowflow.memory.long_term import LongTermMemoryManager
from knowflow.memory.manager import MemoryManager
from knowflow.memory.short_term import ShortTermMemory
from knowflow.schemas.memory import MemoryItem, MemorySedimentRequest

router = APIRouter(prefix="/memory", tags=["memory"])


def _build_manager(db: Any, redis: Any, llm: Any, embedding: Any) -> MemoryManager:
    """装配记忆管理器(与 chat 端点一致)."""
    return MemoryManager(
        short_term=ShortTermMemory(redis),
        importance=ImportanceScorer(llm),
        compressor=Compressor(llm),
        long_term=LongTermMemoryManager(db, embedding_client=embedding),
    )


def _to_item(memory: Any) -> MemoryItem:
    """ORM 记忆 → 响应 Schema."""
    return MemoryItem(
        id=int(memory.id),
        user_id=memory.user_id,
        session_id=int(memory.session_id),
        content=memory.content,
        summary=memory.summary,
        importance=memory.importance,
        created_at=memory.created_at,
        last_recall=memory.last_recall,
    )


@router.get("/{user_id}", response_model=list[MemoryItem])
async def list_memory(
    user_id: str,
    db: DbDep,
    redis: RedisDep,
    llm: LlmDep,
    embedding: EmbeddingDep,
) -> list[MemoryItem]:
    """列出用户全部长期记忆(按创建时间)."""
    manager = _build_manager(db, redis, llm, embedding)
    memories = await manager.list_by_user(user_id)
    return [_to_item(m) for m in memories]


@router.delete("/{user_id}/{memory_id}")
async def delete_memory(
    user_id: str,
    memory_id: int,
    db: DbDep,
    redis: RedisDep,
    llm: LlmDep,
    embedding: EmbeddingDep,
) -> dict[str, bool]:
    """删除单条记忆; 不存在返回 404."""
    manager = _build_manager(db, redis, llm, embedding)
    deleted = await manager.delete(memory_id)
    await db.commit()
    if not deleted:
        raise NotFoundError(f"记忆不存在: memory_id={memory_id}")
    return {"deleted": True}


@router.post("/{user_id}/sediment", response_model=dict[str, int])
async def sediment_memory(
    user_id: str,
    req: MemorySedimentRequest,
    db: DbDep,
    redis: RedisDep,
    llm: LlmDep,
    embedding: EmbeddingDep,
) -> dict[str, int]:
    """手动沉淀: 筛选会话短期记忆中高价值消息, 压缩后写入长期记忆."""
    manager = _build_manager(db, redis, llm, embedding)
    saved = await manager.sediment(req.session_id, user_id)
    await db.commit()
    return {"saved": saved}
