"""Entity / Relation / EntityAlias 数据访问层 + 一跳扩展查询.

一跳扩展核心 SQL(对齐设计文档 3.4 模块一):
    SELECT DISTINCT c.id FROM chunks c
    JOIN entities e ON e.chunk_id = c.id
    JOIN relations r ON r.source_entity_id = e.id
    JOIN entities e2 ON r.target_entity_id = e2.id
    JOIN chunks c2 ON e2.chunk_id = c2.id
    WHERE e.id = ANY(:entity_ids) AND c.id <> c2.id

SQLite 不支持 ANY(), 改用 IN; SQLAlchemy 自动按方言生成.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.models.graph import Entity, EntityAlias, Relation


class EntityRepo:
    """实体 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        doc_id: int,
        chunk_id: int,
        name: str,
        entity_type: str,
        normalized: str | None = None,
    ) -> Entity:
        """新建实体. normalized 缺省取 name."""
        entity = Entity(
            doc_id=doc_id,
            chunk_id=chunk_id,
            name=name,
            entity_type=entity_type,
            normalized=normalized or name,
        )
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def bulk_create(self, entities: list[Entity]) -> list[Entity]:
        """批量建实体."""
        self.session.add_all(entities)
        await self.session.flush()
        for entity in entities:
            await self.session.refresh(entity)
        return entities

    async def list_by_chunk(self, chunk_id: int) -> Sequence[Entity]:
        """按 chunk 列出实体."""
        stmt = select(Entity).where(Entity.chunk_id == chunk_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_by_normalized(self, normalized: str) -> Sequence[Entity]:
        """按归一化名称查实体(用于实体归一与合并)."""
        stmt = select(Entity).where(Entity.normalized == normalized)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_many(self, entity_ids: Sequence[int]) -> Sequence[Entity]:
        """按 id 列表批量获取."""
        if not entity_ids:
            return []
        stmt = select(Entity).where(Entity.id.in_(entity_ids))
        result = await self.session.execute(stmt)
        return result.scalars().all()


class EntityAliasRepo:
    """实体别名 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, entity_id: int, alias: str) -> EntityAlias:
        """新建别名. UNIQUE(entity_id, alias) 由 DB 保证."""
        alias_obj = EntityAlias(entity_id=entity_id, alias=alias)
        self.session.add(alias_obj)
        await self.session.flush()
        await self.session.refresh(alias_obj)
        return alias_obj

    async def list_by_entity(self, entity_id: int) -> Sequence[EntityAlias]:
        """按实体列出别名."""
        stmt = select(EntityAlias).where(EntityAlias.entity_id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class RelationRepo:
    """关系 CRUD + 一跳扩展查询."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        doc_id: int,
        source_entity_id: int,
        target_entity_id: int,
        relation_type: str,
        confidence: float = 1.0,
    ) -> Relation:
        """新建关系."""
        rel = Relation(
            doc_id=doc_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            confidence=confidence,
        )
        self.session.add(rel)
        await self.session.flush()
        await self.session.refresh(rel)
        return rel

    async def bulk_create(self, relations: list[Relation]) -> list[Relation]:
        """批量建关系."""
        self.session.add_all(relations)
        await self.session.flush()
        for rel in relations:
            await self.session.refresh(rel)
        return relations

    async def list_by_source(self, source_entity_id: int) -> Sequence[Relation]:
        """按源实体列出关系(出边)."""
        stmt = select(Relation).where(Relation.source_entity_id == source_entity_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def one_hop_expand(self, entity_ids: Sequence[int]) -> list[int]:
        """一跳扩展: 给定一组实体 id, 返回关联但不同的 chunk_id 列表.

        对齐设计文档 3.4 一跳扩展查询:
            e --r--> e2 --c2  返回 c2 的 chunk_id
        输入 entity_ids 为空时返回空列表.
        """
        if not entity_ids:
            return []

        # 子查询: 找出源实体通过关系指向的目标实体 id
        target_ids_subq = (
            select(Relation.target_entity_id)
            .where(Relation.source_entity_id.in_(entity_ids))
            .distinct()
        )
        # 主查询: 取目标实体所属的 chunk_id(剔除输入实体本身的 chunk)
        input_chunks_subq = select(Entity.chunk_id).where(Entity.id.in_(entity_ids))
        stmt = (
            select(Entity.chunk_id)
            .where(Entity.id.in_(target_ids_subq))
            .where(Entity.chunk_id.not_in(input_chunks_subq))
            .distinct()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
