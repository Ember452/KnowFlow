"""EntityRepo / EntityAliasRepo / RelationRepo 单测, 重点验证一跳扩展查询."""

import pytest

from knowflow.db.repositories.document_repo import ChunkRepo, DocumentRepo
from knowflow.db.repositories.graph_repo import (
    EntityAliasRepo,
    EntityRepo,
    RelationRepo,
)
from knowflow.models.graph import Entity


@pytest.mark.asyncio
async def test_entity_create_defaults_normalized(db_session) -> None:  # type: ignore[no-untyped-def]
    """normalized 缺省取 name."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk = await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    await db_session.commit()

    entity = await entity_repo.create(
        doc_id=doc.id, chunk_id=chunk.id, name="OpenAI", entity_type="org"
    )
    await db_session.commit()
    assert entity.normalized == "OpenAI"


@pytest.mark.asyncio
async def test_entity_bulk_create(db_session) -> None:  # type: ignore[no-untyped-def]
    """批量建实体."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk = await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    await db_session.commit()

    entities = [
        Entity(
            doc_id=doc.id,
            chunk_id=chunk.id,
            name=f"e{i}",
            entity_type="concept",
            normalized=f"e{i}",
        )
        for i in range(3)
    ]
    created = await entity_repo.bulk_create(entities)
    await db_session.commit()

    assert all(e.id is not None for e in created)
    assert len(await entity_repo.list_by_chunk(chunk.id)) == 3


@pytest.mark.asyncio
async def test_entity_find_by_normalized(db_session) -> None:  # type: ignore[no-untyped-def]
    """按归一化名称查实体."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk = await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    await entity_repo.create(doc_id=doc.id, chunk_id=chunk.id, name="OpenAI", entity_type="org")
    await entity_repo.create(
        doc_id=doc.id,
        chunk_id=chunk.id,
        name="OpenAI",
        entity_type="org",
        normalized="openai",
    )
    await db_session.commit()

    by_name = await entity_repo.find_by_normalized("OpenAI")
    assert len(by_name) == 1
    by_norm = await entity_repo.find_by_normalized("openai")
    assert len(by_norm) == 1


@pytest.mark.asyncio
async def test_alias_unique_constraint(db_session) -> None:  # type: ignore[no-untyped-def]
    """同 (entity_id, alias) 重复插入应触发 UNIQUE 约束."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)
    alias_repo = EntityAliasRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk = await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    entity = await entity_repo.create(
        doc_id=doc.id, chunk_id=chunk.id, name="GPT", entity_type="model"
    )
    await db_session.commit()

    await alias_repo.create(entity_id=entity.id, alias="ChatGPT")
    await db_session.commit()

    with pytest.raises(Exception):  # noqa: B017
        await alias_repo.create(entity_id=entity.id, alias="ChatGPT")
        await db_session.commit()


@pytest.mark.asyncio
async def test_one_hop_expand_returns_neighbor_chunks(db_session) -> None:  # type: ignore[no-untyped-def]
    """一跳扩展: e1 --r--> e2, 返回 e2 所属 chunk 但不返回 e1 的 chunk."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)
    rel_repo = RelationRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    # 两个 chunk, 各持有一个实体
    c1 = await chunk_repo.create(doc_id=doc.id, content="chunk1", chunk_index=0, token_count=1)
    c2 = await chunk_repo.create(doc_id=doc.id, content="chunk2", chunk_index=1, token_count=1)
    await db_session.commit()

    e1 = await entity_repo.create(doc_id=doc.id, chunk_id=c1.id, name="Alice", entity_type="person")
    e2 = await entity_repo.create(doc_id=doc.id, chunk_id=c2.id, name="Bob", entity_type="person")
    await rel_repo.create(
        doc_id=doc.id,
        source_entity_id=e1.id,
        target_entity_id=e2.id,
        relation_type="related_to",
    )
    await db_session.commit()

    expanded = await rel_repo.one_hop_expand([e1.id])
    assert expanded == [c2.id]


@pytest.mark.asyncio
async def test_one_hop_expand_excludes_self_chunk(db_session) -> None:  # type: ignore[no-untyped-def]
    """一跳扩展应剔除输入实体本身的 chunk."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)
    rel_repo = RelationRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    c1 = await chunk_repo.create(doc_id=doc.id, content="chunk1", chunk_index=0, token_count=1)
    await db_session.commit()

    # 同一 chunk 内两个实体自环关系
    e1 = await entity_repo.create(doc_id=doc.id, chunk_id=c1.id, name="A", entity_type="concept")
    e2 = await entity_repo.create(doc_id=doc.id, chunk_id=c1.id, name="B", entity_type="concept")
    await rel_repo.create(
        doc_id=doc.id,
        source_entity_id=e1.id,
        target_entity_id=e2.id,
        relation_type="part_of",
    )
    await db_session.commit()

    # e1 -> e2 都属于 c1, 应被剔除
    assert await rel_repo.one_hop_expand([e1.id]) == []


@pytest.mark.asyncio
async def test_one_hop_expand_empty_input(db_session) -> None:  # type: ignore[no-untyped-def]
    """空实体 id 列表直接返回空."""
    rel_repo = RelationRepo(db_session)
    assert await rel_repo.one_hop_expand([]) == []


@pytest.mark.asyncio
async def test_relation_list_by_source(db_session) -> None:  # type: ignore[no-untyped-def]
    """按源实体列出关系."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    entity_repo = EntityRepo(db_session)
    rel_repo = RelationRepo(db_session)

    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    c1 = await chunk_repo.create(doc_id=doc.id, content="c1", chunk_index=0, token_count=1)
    c2 = await chunk_repo.create(doc_id=doc.id, content="c2", chunk_index=1, token_count=1)
    c3 = await chunk_repo.create(doc_id=doc.id, content="c3", chunk_index=2, token_count=1)
    await db_session.commit()

    e1 = await entity_repo.create(doc_id=doc.id, chunk_id=c1.id, name="A", entity_type="concept")
    e2 = await entity_repo.create(doc_id=doc.id, chunk_id=c2.id, name="B", entity_type="concept")
    e3 = await entity_repo.create(doc_id=doc.id, chunk_id=c3.id, name="C", entity_type="concept")
    await rel_repo.create(
        doc_id=doc.id,
        source_entity_id=e1.id,
        target_entity_id=e2.id,
        relation_type="r1",
    )
    await rel_repo.create(
        doc_id=doc.id,
        source_entity_id=e1.id,
        target_entity_id=e3.id,
        relation_type="r2",
    )
    await db_session.commit()

    rels = await rel_repo.list_by_source(e1.id)
    assert len(rels) == 2
    assert {r.relation_type for r in rels} == {"r1", "r2"}
