"""知识检索端点单测 - /knowledge/search 调 retriever(可通过 set_retriever 替换)."""

from fastapi.testclient import TestClient

from knowflow.api import deps
from tests.fakes import FakeChunkWithScore, FakeRetriever


def test_search_returns_chunks(client: TestClient) -> None:
    """检索返回 fake retriever 预设的 chunk."""
    chunks = [FakeChunkWithScore(chunk_id=1, content="答案", score=0.9, source="hybrid")]
    deps.set_retriever(FakeRetriever(chunks=chunks))
    resp = client.post("/api/v1/knowledge/search", json={"query": "测试", "top_k": 5})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["query"] == "测试"
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["chunk_id"] == 1
    assert data["chunks"][0]["content"] == "答案"
    assert data["total"] == 1


def test_search_validates_empty_query(client: TestClient) -> None:
    """空 query 校验失败返回 422."""
    resp = client.post("/api/v1/knowledge/search", json={"query": ""})
    assert resp.status_code == 422


def test_search_passes_flags(client: TestClient) -> None:
    """with_expand/with_rerank 透传给 retriever."""
    retriever = FakeRetriever(chunks=[])
    deps.set_retriever(retriever)
    client.post(
        "/api/v1/knowledge/search",
        json={"query": "q", "with_expand": False, "with_rerank": False},
    )
    assert retriever.calls[0]["with_expand"] is False
    assert retriever.calls[0]["with_rerank"] is False
