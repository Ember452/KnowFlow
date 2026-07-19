"""索引全链路集成测试 - HTTP 上传 → 投递任务 → worker 消费 → 文档转 ready.

不依赖真实容器: get_db 用 SQLite, MinIO/Embedding/VectorStore/BM25/Extractor 用 fake,
broker 用 FakeBroker 捕获任务, 再调 handle_index_task 模拟 worker 消费.
真实容器(真实 Milvus/LLM/MinIO)的端到端验收见 docs/tests/指标测试-API与异步索引.md.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.api import deps
from knowflow.db.repositories.document_repo import ChunkRepo, DocumentIndexRepo, DocumentRepo
from knowflow.main import create_app
from knowflow.retrieval.bm25_store import BM25Doc
from knowflow.retrieval.entity_extractor import ExtractResult
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.pipeline import IndexDeps
from knowflow.retrieval.vector_store import ChunkVector
from knowflow.tasks.index_task import handle_index_task
from tests.fakes import FakeBroker, FakeMinio


class _FakeEmbedding:
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[float(len(t)), 0.0] for t in texts]

    def embed_one(self, text: str) -> list[float]:
        return [float(len(text)), 0.0]


class _FakeExtractor:
    def extract(self, chunk_text: str) -> ExtractResult:
        return ExtractResult()


class _FakeVectorStore:
    def upsert(self, chunks: Sequence[ChunkVector]) -> int:
        return len(chunks)

    def delete_by_doc(self, doc_id: int) -> int:
        return 0


class _FakeBM25Store:
    def add_batch(self, docs: Sequence[BM25Doc]) -> None:
        return None

    def delete_by_doc(self, doc_id: int) -> int:
        return 0


def _build_deps(session: AsyncSession, minio: Any) -> IndexDeps:
    return IndexDeps(
        session=session,
        document_repo=DocumentRepo(session),
        chunk_repo=ChunkRepo(session),
        document_index_repo=DocumentIndexRepo(session),
        graph_store=GraphStore(session),
        vector_store=_FakeVectorStore(),
        bm25_store=_FakeBM25Store(),
        embedding_client=_FakeEmbedding(),
        entity_extractor=_FakeExtractor(),
        minio_client=minio,
        bucket="b",
    )


@pytest.mark.asyncio
async def test_index_full_pipeline_via_api(api_session_factory) -> None:
    """HTTP 上传 → 任务入队 → worker 消费 → 文档 ready, 全链路在 SQLite+fake 上跑通."""
    minio = FakeMinio()
    broker = FakeBroker()
    app = create_app()

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with api_session_factory() as session:
            yield session

    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[deps.get_redis_dep] = lambda: object()
    app.dependency_overrides[deps.get_minio_dep] = lambda: minio
    app.dependency_overrides[deps.get_broker_dep] = lambda: broker

    client = TestClient(app)

    # 1. 上传: pending + 投递索引任务
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("doc.md", "# 报销流程\n提交发票给财务".encode(), "text/markdown")},
        headers={"X-User-Id": "u1"},
    )
    assert resp.status_code == 200
    doc_id = resp.json()["data"]["doc_id"]
    assert len(broker.enqueued) == 1
    task_payload = broker.enqueued[0][1]
    assert task_payload["task"] == "index"
    assert task_payload["doc_id"] == doc_id

    # 2. 列表: 状态 pending
    lst = client.get("/api/v1/documents", headers={"X-User-Id": "u1"}).json()["data"]
    assert lst["items"][0]["status"] == "pending"

    # 3. 模拟 worker 消费任务
    with patch("knowflow.db.base.get_session_factory", return_value=api_session_factory):
        result = await handle_index_task(task_payload, lambda s: _build_deps(s, minio))
    assert result["ok"] is True
    assert result["result"].chunk_count >= 1

    # 4. 列表: 状态 ready
    lst2 = client.get("/api/v1/documents", headers={"X-User-Id": "u1"}).json()["data"]
    assert lst2["items"][0]["status"] == "ready"
    assert lst2["items"][0]["id"] == doc_id
