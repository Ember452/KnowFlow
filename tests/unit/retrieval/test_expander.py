"""expander 单测 - 用 db_session fixture 真跑 SQLite, 验证一跳扩展 / 自环剔除 / 去重."""

import pytest

from knowflow.db.repositories.document_repo import ChunkRepo, DocumentRepo
from knowflow.retrieval.entity_extractor import Entity as ExtractedEntity
from knowflow.retrieval.entity_extractor import Relation as ExtractedRelation
from knowflow.retrieval.expander import Expander
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.hybrid_search import ChunkScore


async def _setup_doc_with_chunks(
    db_session,  # type: ignore[no-untyped-def]
) -> tuple[int, int, int]:
    """构造 1 doc + 2 chunks, 返回 (doc_id, chunk1_id, chunk2_id)."""
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
    return doc.id, chunk1.id, chunk2.id


@pytest.mark.asyncio
async def test_expand_finds_related_chunk(db_session) -> None:  # type: ignore[no-untyped-def]
    """一跳扩展: 从 chunk1 的实体出发, 找到 chunk2."""
    doc_id, chunk1_id, chunk2_id = await _setup_doc_with_chunks(db_session)
    store = GraphStore(db_session)

    # chunk1: 张三
    e1 = await store.upsert_entities(
        doc_id,
        chunk1_id,
        [ExtractedEntity(name="张三", type="person", normalized="张三")],
    )
    # chunk2: 财务部(共享实体), 李四
    e2 = await store.upsert_entities(
        doc_id,
        chunk2_id,
        [ExtractedEntity(name="财务部", type="org", normalized="财务部")],
    )
    # 关系: 张三 -> 财务部
    name_to_id = {ent.name: ent.id for ent in [*e1, *e2]}
    await store.upsert_relations(
        doc_id,
        [ExtractedRelation(source="张三", target="财务部", relation_type="belongs_to")],
        name_to_id,
    )
    await db_session.commit()

    # 模拟 hybrid 命中 chunk1
    hits = [ChunkScore(chunk_id=chunk1_id, score=0.5, source="hybrid")]
    expander = Expander(db_session, graph_store=store)
    result = await expander.expand(hits)

    # 应返回 chunk1(原始) + chunk2(扩展)
    assert len(result) == 2
    assert result[0].chunk_id == chunk1_id
    assert result[0].source == "hybrid"
    assert result[0].score == 0.5
    assert result[1].chunk_id == chunk2_id
    assert result[1].source == "expand"
    assert result[1].score == 0.0


@pytest.mark.asyncio
async def test_expand_empty_hits(db_session) -> None:  # type: ignore[no-untyped-def]
    """空 hits 返回空列表."""
    expander = Expander(db_session)
    assert await expander.expand([]) == []


@pytest.mark.asyncio
async def test_expand_no_entities(db_session) -> None:  # type: ignore[no-untyped-def]
    """命中 chunk 无实体时, 直接返回原 hits."""
    _doc_id, chunk1_id, _ = await _setup_doc_with_chunks(db_session)
    # 不写任何实体
    await db_session.commit()

    hits = [ChunkScore(chunk_id=chunk1_id, score=0.5, source="hybrid")]
    expander = Expander(db_session)
    result = await expander.expand(hits)
    assert len(result) == 1
    assert result[0].chunk_id == chunk1_id
    assert result[0].source == "hybrid"


@pytest.mark.asyncio
async def test_expand_self_loop_excluded(db_session) -> None:  # type: ignore[no-untyped-def]
    """扩展结果排除原始 hits 中的 chunk(自环剔除)."""
    doc_id, chunk1_id, chunk2_id = await _setup_doc_with_chunks(db_session)
    store = GraphStore(db_session)

    # chunk1 和 chunk2 都有 "共享实体"
    e1 = await store.upsert_entities(
        doc_id,
        chunk1_id,
        [ExtractedEntity(name="共享", type="concept", normalized="共享")],
    )
    e2 = await store.upsert_entities(
        doc_id,
        chunk2_id,
        [ExtractedEntity(name="共享", type="concept", normalized="共享")],
    )
    # 互相关联
    name_to_id = {ent.name: ent.id for ent in [*e1, *e2]}
    await store.upsert_relations(
        doc_id,
        [
            ExtractedRelation(source="共享", target="共享", relation_type="related_to"),
        ],
        name_to_id,
    )
    await db_session.commit()

    # chunk1 命中, 扩展到 chunk2(chunk2 也有 "共享" 实体)
    # 但 chunk1 本身不应在扩展结果中(自环剔除)
    hits = [
        ChunkScore(chunk_id=chunk1_id, score=0.5, source="hybrid"),
        ChunkScore(chunk_id=chunk2_id, score=0.3, source="hybrid"),
    ]
    expander = Expander(db_session, graph_store=store)
    result = await expander.expand(hits)

    # 原始 2 条 + 可能的扩展
    chunk_ids = [r.chunk_id for r in result]
    # chunk1 和 chunk2 都在原始 hits 中, 不应出现重复
    assert chunk_ids.count(chunk1_id) == 1
    assert chunk_ids.count(chunk2_id) == 1


@pytest.mark.asyncio
async def test_expand_dedup_with_original(db_session) -> None:  # type: ignore[no-untyped-def]
    """扩展 chunk 与原始 hits 去重."""
    doc_id, chunk1_id, chunk2_id = await _setup_doc_with_chunks(db_session)
    store = GraphStore(db_session)

    e1 = await store.upsert_entities(
        doc_id,
        chunk1_id,
        [ExtractedEntity(name="张三", type="person", normalized="张三")],
    )
    e2 = await store.upsert_entities(
        doc_id,
        chunk2_id,
        [ExtractedEntity(name="财务部", type="org", normalized="财务部")],
    )
    name_to_id = {ent.name: ent.id for ent in [*e1, *e2]}
    await store.upsert_relations(
        doc_id,
        [ExtractedRelation(source="张三", target="财务部", relation_type="belongs_to")],
        name_to_id,
    )
    await db_session.commit()

    # chunk1 和 chunk2 都在原始 hits 中
    hits = [
        ChunkScore(chunk_id=chunk1_id, score=0.5, source="hybrid"),
        ChunkScore(chunk_id=chunk2_id, score=0.3, source="hybrid"),
    ]
    expander = Expander(db_session, graph_store=store)
    result = await expander.expand(hits)

    # 扩展应找到 chunk2, 但它已在 hits 中, 不应重复添加
    assert len(result) == 2
    chunk_ids = [r.chunk_id for r in result]
    assert chunk_ids.count(chunk1_id) == 1
    assert chunk_ids.count(chunk2_id) == 1
