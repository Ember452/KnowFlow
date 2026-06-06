"""一跳扩展 - 从命中 chunk 出发, 通过实体关系找到关联 chunk, 提升召回率.

流程: hits -> find_entity_ids_by_chunk 收集 entity_ids -> one_hop_expand 取关联
chunk_ids -> ChunkRepo.get_many 取 chunk 内容 -> 构造 ChunkScore(source="expand") 合并去重.

扩展 chunk 分数置 0(排在原始 hits 之后), 保留原始 hits 分数.
"""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.db.repositories.document_repo import ChunkRepo
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.hybrid_search import ChunkScore


class Expander:
    """一跳扩展器. 通过实体关系扩展检索结果."""

    def __init__(self, session: AsyncSession, graph_store: GraphStore | None = None) -> None:
        """初始化.

        Args:
            session: 异步 DB 会话.
            graph_store: 图谱存储(可注入, 默认用 session 构造).
        """
        self.session = session
        self.graph_store = graph_store or GraphStore(session)
        self.chunk_repo = ChunkRepo(session)

    async def expand(self, hits: Sequence[ChunkScore]) -> list[ChunkScore]:
        """对命中结果做一跳扩展.

        Args:
            hits: 原始检索结果(hybrid 阶段输出).

        Returns:
            合并去重后的 ChunkScore 列表:
            - 原始 hits 保留原分数与 source
            - 扩展 chunk 追加在后, score=0.0, source="expand"
        """
        if not hits:
            return []

        # 收集所有命中 chunk 的 entity_ids
        original_chunk_ids = {h.chunk_id for h in hits}
        all_entity_ids: list[int] = []
        for h in hits:
            entity_ids = await self.graph_store.find_entity_ids_by_chunk(h.chunk_id)
            all_entity_ids.extend(entity_ids)

        if not all_entity_ids:
            # 无实体, 直接返回原 hits
            return list(hits)

        # 一跳扩展: 取关联 chunk_ids
        expanded_chunk_ids = await self.graph_store.one_hop_expand(all_entity_ids)

        # 去重: 排除已在原 hits 中的 chunk
        new_chunk_ids = [cid for cid in expanded_chunk_ids if cid not in original_chunk_ids]
        if not new_chunk_ids:
            return list(hits)

        # 验证扩展 chunk 确实存在(get_many 返回的 ORM 列表)
        expanded_chunks = await self.chunk_repo.get_many(new_chunk_ids)
        existing_ids = {c.id for c in expanded_chunks}

        # 构造结果: 原 hits + 扩展 chunk(score=0, source="expand")
        result: list[ChunkScore] = list(hits)
        for cid in new_chunk_ids:
            if cid in existing_ids:
                result.append(ChunkScore(chunk_id=cid, score=0.0, source="expand"))
        return result
