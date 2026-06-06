"""graph_store 单测 - 用 db_session fixture 真跑 SQLite, 验证实体/关系写入与一跳扩展联动."""

import pytest

from knowflow.db.repositories.document_repo import ChunkRepo, DocumentRepo
from knowflow.retrieval.entity_extractor import Entity as ExtractedEntity
from knowflow.retrieval.entity_extractor import Relation as ExtractedRelation
from knowflow.retrieval.graph_store import GraphStore


@pytest.mark.asyncio
async def test_upsert_entities_returns_orm_with_id(db_session) -> None:  # type: ignore[no-untyped-def]
    """upsert_entities 返回 ORM Entity 列表, 含 id 字段."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk = await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    await db_session.commit()

    store = GraphStore(db_session)
    extracted = [
        ExtractedEntity(name="张三", type="person", normalized="张三"),
        ExtractedEntity(name="财务部", type="org", normalized="财务部"),
    ]
    orm_entities = await store.upsert_entities(doc.id, chunk.id, extracted)
    await db_session.commit()

    assert len(orm_entities) == 2
    assert all(e.id is not None for e in orm_entities)
    assert orm_entities[0].name == "张三"
    assert orm_entities[0].normalized == "张三"
    assert orm_entities[1].name == "财务部"


@pytest.mark.asyncio
async def test_upsert_entities_empty(db_session) -> None:  # type: ignore[no-untyped-def]
    """空实体列表返回空列表."""
    store = GraphStore(db_session)
    result = await store.upsert_entities(1, 1, [])
    assert result == []


@pytest.mark.asyncio
async def test_upsert_relations_resolves_entity_ids(db_session) -> None:  # type: ignore[no-untyped-def]
    """upsert_relations 按 name 解析 entity_id, 写入 Relation."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk = await chunk_repo.create(doc_id=doc.id, content="c", chunk_index=0, token_count=1)
    await db_session.commit()

    store = GraphStore(db_session)
    extracted_entities = [
        ExtractedEntity(name="张三", type="person", normalized="张三"),
        ExtractedEntity(name="财务部", type="org", normalized="财务部"),
    ]
    orm_entities = await store.upsert_entities(doc.id, chunk.id, extracted_entities)
    name_to_id = {e.name: e.id for e in orm_entities}

    extracted_relations = [
        ExtractedRelation(source="张三", target="财务部", relation_type="belongs_to")
    ]
    orm_relations = await store.upsert_relations(doc.id, extracted_relations, name_to_id)
    await db_session.commit()

    assert len(orm_relations) == 1
    assert orm_relations[0].source_entity_id == name_to_id["张三"]
    assert orm_relations[0].target_entity_id == name_to_id["财务部"]
    assert orm_relations[0].relation_type == "belongs_to"


@pytest.mark.asyncio
async def test_upsert_relations_skips_unresolved(db_session) -> None:  # type: ignore[no-untyped-def]
    """关系端点未在实体列表中时跳过, 不抛异常."""
    store = GraphStore(db_session)
    relations = [ExtractedRelation(source="未知实体", target="另一个", relation_type="related_to")]
    # 空的 entity_name_to_id, 两个端点都解析失败
    result = await store.upsert_relations(1, relations, {})
    assert result == []


@pytest.mark.asyncio
async def test_one_hop_expand_e2e(db_session) -> None:  # type: ignore[no-untyped-def]
    """端到端: 两 chunk 通过实体关系一跳扩展."""
    doc_repo = DocumentRepo(db_session)
    chunk_repo = ChunkRepo(db_session)
    doc = await doc_repo.create(title="d", source_uri="a", file_type="pdf", size_bytes=1)
    chunk1 = await chunk_repo.create(
        doc_id=doc.id, content="张三在财务部", chunk_index=0, token_count=5
    )
    chunk2 = await chunk_repo.create(
        doc_id=doc.id, content="李四在技术部", chunk_index=1, token_count=5
    )
    await db_session.commit()

    store = GraphStore(db_session)
    # chunk1: 张三 -> 财务部
    e1 = await store.upsert_entities(
        doc.id,
        chunk1.id,
        [ExtractedEntity(name="张三", type="person", normalized="张三")],
    )
    # chunk2: 财务部(同实体), 李四
    e2 = await store.upsert_entities(
        doc.id,
        chunk2.id,
        [ExtractedEntity(name="财务部", type="org", normalized="财务部")],
    )
    # 关系: 张三 -> 财务部
    name_to_id = {ent.name: ent.id for ent in [*e1, *e2]}
    await store.upsert_relations(
        doc.id,
        [ExtractedRelation(source="张三", target="财务部", relation_type="belongs_to")],
        name_to_id,
    )
    await db_session.commit()

    # 一跳扩展: 从 chunk1 的实体(张三) 出发, 通过关系找到 财务部 所属 chunk2
    entity_ids = await store.find_entity_ids_by_chunk(chunk1.id)
    assert len(entity_ids) == 1  # 张三
    expanded = await store.one_hop_expand(entity_ids)
    assert chunk2.id in expanded
    # 自环剔除: chunk1 不在结果中
    assert chunk1.id not in expanded


@pytest.mark.asyncio
async def test_find_entity_ids_by_chunk_empty(db_session) -> None:  # type: ignore[no-untyped-def]
    """无实体的 chunk 返回空列表."""
    store = GraphStore(db_session)
    result = await store.find_entity_ids_by_chunk(9999)
    assert result == []


@pytest.mark.asyncio
async def test_one_hop_expand_empty_input(db_session) -> None:  # type: ignore[no-untyped-def]
    """空 entity_ids 返回空列表."""
    store = GraphStore(db_session)
    assert await store.one_hop_expand([]) == []
