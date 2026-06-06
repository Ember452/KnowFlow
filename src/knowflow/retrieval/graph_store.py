"""图谱存储 - 封装 EntityRepo/RelationRepo, 提供索引时实体关系写入与一跳扩展查询.

薄封装层, 复用 M1 已实现的 repo, 不引入新 SQL. 事务由调用方(pipeline)管理.
"""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.db.repositories.graph_repo import EntityRepo, RelationRepo
from knowflow.models.graph import Entity, Relation
from knowflow.retrieval.entity_extractor import Entity as ExtractedEntity
from knowflow.retrieval.entity_extractor import Relation as ExtractedRelation


class GraphStore:
    """图谱存储. 封装实体/关系写入与一跳扩展查询."""

    def __init__(self, session: AsyncSession) -> None:
        """初始化.

        Args:
            session: 异步 DB 会话, 事务由调用方管理.
        """
        self.session = session
        self.entity_repo = EntityRepo(session)
        self.relation_repo = RelationRepo(session)

    async def upsert_entities(
        self,
        doc_id: int,
        chunk_id: int,
        entities: Sequence[ExtractedEntity],
    ) -> list[Entity]:
        """批量建实体(每个 chunk 抽取的实体一次写入).

        Args:
            doc_id: 所属文档 id.
            chunk_id: 所属分块 id.
            entities: 抽取器返回的实体列表(已归一化).

        Returns:
            写入后的 Entity ORM 列表(含 id, 用于建关系).
        """
        if not entities:
            return []
        orm_entities = [
            Entity(
                doc_id=doc_id,
                chunk_id=chunk_id,
                name=e.name,
                entity_type=e.type,
                normalized=e.normalized or e.name.lower(),
            )
            for e in entities
        ]
        created: list[Entity] = await self.entity_repo.bulk_create(orm_entities)
        return created

    async def upsert_relations(
        self,
        doc_id: int,
        relations: Sequence[ExtractedRelation],
        entity_name_to_id: dict[str, int],
    ) -> list[Relation]:
        """批量建关系. 按 name 解析 entity_id, 跳过未解析的关系.

        Args:
            doc_id: 所属文档 id.
            relations: 抽取器返回的关系列表.
            entity_name_to_id: 实体 name -> entity_id 映射(由 upsert_entities 返回构造).

        Returns:
            写入后的 Relation ORM 列表.
        """
        orm_relations: list[Relation] = []
        for r in relations:
            source_id = entity_name_to_id.get(r.source)
            target_id = entity_name_to_id.get(r.target)
            if source_id is None or target_id is None:
                # 关系端点未在实体列表中出现, 跳过(不抛异常, 不阻塞索引)
                continue
            orm_relations.append(
                Relation(
                    doc_id=doc_id,
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relation_type=r.relation_type,
                )
            )
        if not orm_relations:
            return []
        created_rels: list[Relation] = await self.relation_repo.bulk_create(orm_relations)
        return created_rels

    async def find_entity_ids_by_chunk(self, chunk_id: int) -> list[int]:
        """按 chunk_id 查实体 id 列表."""
        entities = await self.entity_repo.list_by_chunk(chunk_id)
        return [e.id for e in entities]

    async def one_hop_expand(self, entity_ids: Sequence[int]) -> list[int]:
        """透传 RelationRepo.one_hop_expand: 给定实体 id 返回关联 chunk_id 列表."""
        expanded: list[int] = await self.relation_repo.one_hop_expand(entity_ids)
        return expanded
