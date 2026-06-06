"""vector_store 单测 - mock MilvusClient, 验证 upsert/search/delete 调用参数与返回解析."""

from typing import Any

from knowflow.retrieval.vector_store import ChunkVector, VectorHit, VectorStore


class FakeMilvusClient:
    """fake MilvusClient: 记录调用参数, 返回预设结果."""

    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []
        self.search_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        # search 默认返回 2 条命中
        self.search_results: list[list[dict[str, Any]]] = [
            [
                {"id": 101, "distance": 0.95},
                {"id": 102, "distance": 0.85},
            ]
        ]

    def upsert(self, *, collection_name: str, data: list[dict[str, Any]]) -> None:
        self.upsert_calls.append({"collection_name": collection_name, "data": data})

    def search(
        self,
        *,
        collection_name: str,
        data: list[list[float]],
        **kwargs: Any,
    ) -> list[list[dict[str, Any]]]:
        self.search_calls.append({"collection_name": collection_name, "data": data, **kwargs})
        return self.search_results

    def delete(self, *, collection_name: str, filter: str) -> None:
        self.delete_calls.append({"collection_name": collection_name, "filter": filter})


def test_upsert_writes_data() -> None:
    """upsert 把 ChunkVector 转为 dict 写入."""
    client = FakeMilvusClient()
    store = VectorStore(client=client, collection_name="test_col")
    chunks = [
        ChunkVector(chunk_id=1, doc_id=10, embedding=[0.1, 0.2]),
        ChunkVector(chunk_id=2, doc_id=10, embedding=[0.3, 0.4]),
    ]
    count = store.upsert(chunks)
    assert count == 2
    assert len(client.upsert_calls) == 1
    call = client.upsert_calls[0]
    assert call["collection_name"] == "test_col"
    assert call["data"][0] == {"id": 1, "doc_id": 10, "embedding": [0.1, 0.2]}
    assert call["data"][1] == {"id": 2, "doc_id": 10, "embedding": [0.3, 0.4]}


def test_upsert_empty_returns_zero() -> None:
    """空列表不调用 Milvus, 返回 0."""
    client = FakeMilvusClient()
    store = VectorStore(client=client, collection_name="test_col")
    assert store.upsert([]) == 0
    assert client.upsert_calls == []


def test_search_returns_hits() -> None:
    """search 返回 VectorHit 列表, 按分数降序."""
    client = FakeMilvusClient()
    store = VectorStore(client=client, collection_name="test_col")
    hits = store.search([0.1, 0.2, 0.3], top_k=5)
    assert len(hits) == 2
    assert isinstance(hits[0], VectorHit)
    assert hits[0].chunk_id == 101
    assert hits[0].score == 0.95
    assert hits[1].chunk_id == 102
    assert hits[1].score == 0.85
    # 验证调用参数
    assert client.search_calls[0]["collection_name"] == "test_col"
    assert client.search_calls[0]["data"] == [[0.1, 0.2, 0.3]]
    assert client.search_calls[0]["limit"] == 5


def test_search_empty_vector_returns_empty() -> None:
    """空查询向量返回空列表, 不调用 Milvus."""
    client = FakeMilvusClient()
    store = VectorStore(client=client, collection_name="test_col")
    assert store.search([], top_k=5) == []
    assert client.search_calls == []


def test_search_empty_results() -> None:
    """Milvus 返回空结果时, 返回空列表."""
    client = FakeMilvusClient()
    client.search_results = []
    store = VectorStore(client=client, collection_name="test_col")
    assert store.search([0.1], top_k=5) == []


def test_delete_by_doc_sends_filter() -> None:
    """delete_by_doc 发送 filter 表达式."""
    client = FakeMilvusClient()
    store = VectorStore(client=client, collection_name="test_col")
    store.delete_by_doc(42)
    assert len(client.delete_calls) == 1
    assert client.delete_calls[0]["filter"] == "doc_id == 42"
    assert client.delete_calls[0]["collection_name"] == "test_col"
