"""reranker 单测 - mock CrossEncoder, 验证排序 / top_k 截断 / 空输入."""

from dataclasses import dataclass

from knowflow.retrieval.reranker import Reranker


@dataclass
class FakeChunk:
    """fake Chunk ORM, 含 id 与 content."""

    id: int
    content: str


class FakeCrossEncoder:
    """fake CrossEncoder: 按 (query, content) 对返回预设分数."""

    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.predict_calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.predict_calls.append(pairs)
        return self.scores


def test_rerank_orders_by_score_desc() -> None:
    """按分数降序排列."""
    fake = FakeCrossEncoder(scores=[0.3, 0.9, 0.5])
    reranker = Reranker(model=fake)
    chunks = [
        FakeChunk(id=1, content="a"),
        FakeChunk(id=2, content="b"),
        FakeChunk(id=3, content="c"),
    ]
    result = reranker.rerank("query", chunks, top_k=10)

    assert len(result) == 3
    # 分数 0.9 对应 chunk 2, 应排第一
    assert result[0].chunk_id == 2
    assert result[0].score == 0.9
    assert result[1].chunk_id == 3
    assert result[1].score == 0.5
    assert result[2].chunk_id == 1
    assert result[2].score == 0.3
    assert all(r.source == "rerank" for r in result)


def test_rerank_top_k_truncation() -> None:
    """top_k 截断: 返回不超过 top_k 条."""
    fake = FakeCrossEncoder(scores=[0.3, 0.9, 0.5, 0.7])
    reranker = Reranker(model=fake)
    chunks = [FakeChunk(id=i, content=f"c{i}") for i in range(1, 5)]
    result = reranker.rerank("query", chunks, top_k=2)
    assert len(result) == 2
    # 取分数最高的 2 条
    assert result[0].chunk_id == 2  # 0.9
    assert result[1].chunk_id == 4  # 0.7


def test_rerank_empty_chunks() -> None:
    """空 chunks 返回空列表, 不调 model."""
    fake = FakeCrossEncoder(scores=[])
    reranker = Reranker(model=fake)
    assert reranker.rerank("query", [], top_k=5) == []
    assert fake.predict_calls == []


def test_rerank_empty_query() -> None:
    """空查询返回空列表."""
    fake = FakeCrossEncoder(scores=[0.5])
    reranker = Reranker(model=fake)
    chunks = [FakeChunk(id=1, content="a")]
    assert reranker.rerank("", chunks, top_k=5) == []
    assert fake.predict_calls == []


def test_rerank_top_k_zero() -> None:
    """top_k <= 0 返回空列表."""
    fake = FakeCrossEncoder(scores=[0.5])
    reranker = Reranker(model=fake)
    chunks = [FakeChunk(id=1, content="a")]
    assert reranker.rerank("query", chunks, top_k=0) == []


def test_rerank_single_chunk() -> None:
    """单条 chunk 正常返回."""
    fake = FakeCrossEncoder(scores=[0.8])
    reranker = Reranker(model=fake)
    chunks = [FakeChunk(id=1, content="only one")]
    result = reranker.rerank("query", chunks, top_k=5)
    assert len(result) == 1
    assert result[0].chunk_id == 1
    assert result[0].score == 0.8


def test_rerank_pairs_built_correctly() -> None:
    """验证 (query, content) 对被正确构造."""
    fake = FakeCrossEncoder(scores=[0.5, 0.6])
    reranker = Reranker(model=fake)
    chunks = [FakeChunk(id=1, content="hello"), FakeChunk(id=2, content="world")]
    reranker.rerank("test query", chunks, top_k=5)

    assert len(fake.predict_calls) == 1
    pairs = fake.predict_calls[0]
    assert pairs == [("test query", "hello"), ("test query", "world")]


def test_rerank_negative_scores() -> None:
    """负分数也能正确排序."""
    fake = FakeCrossEncoder(scores=[-0.5, -0.1, -0.9])
    reranker = Reranker(model=fake)
    chunks = [
        FakeChunk(id=1, content="a"),
        FakeChunk(id=2, content="b"),
        FakeChunk(id=3, content="c"),
    ]
    result = reranker.rerank("query", chunks, top_k=10)
    # -0.1 > -0.5 > -0.9
    assert result[0].chunk_id == 2
    assert result[1].chunk_id == 1
    assert result[2].chunk_id == 3


# ── 百炼 API 后端 ──


class FakeHttpClient:
    """fake httpx.Client: 记录请求, 返回预设 rerank 响应."""

    def __init__(self, results: list[dict]) -> None:
        self.results = results
        self.post_calls: list[tuple[str, dict, dict]] = []

    def post(self, url: str, *, headers: dict, json: dict) -> "FakeResponse":
        self.post_calls.append((url, headers, json))
        return FakeResponse(self.results)


class FakeResponse:
    """fake httpx.Response: 仅暴露 rerank 需要的方法."""

    def __init__(self, results: list[dict]) -> None:
        self._results = results

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"output": {"results": self._results}}


def test_rerank_api_provider_maps_results() -> None:
    """api provider: 按响应 index 映射 chunk_id, 分数取自 relevance_score."""
    fake = FakeHttpClient(
        results=[{"index": 2, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.4}]
    )
    reranker = Reranker(model_name="qwen3-rerank", provider="api", client=fake)
    chunks = [
        FakeChunk(id=1, content="a"),
        FakeChunk(id=2, content="b"),
        FakeChunk(id=3, content="c"),
    ]
    result = reranker.rerank("query", chunks, top_k=10)
    assert [r.chunk_id for r in result] == [3, 1]
    assert result[0].score == 0.9
    assert all(r.source == "rerank" for r in result)
    # 请求体校验: URL / 鉴权头 / model / input / top_n
    url, headers, body = fake.post_calls[0]
    assert url == "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    assert headers["Authorization"].startswith("Bearer ")
    assert body["model"] == "qwen3-rerank"
    assert body["input"]["query"] == "query"
    assert body["input"]["documents"] == ["a", "b", "c"]
    assert body["parameters"]["top_n"] == 3


def test_rerank_api_top_n_capped() -> None:
    """top_k 大于候选数时 top_n 取候选数(百炼限制)."""
    fake = FakeHttpClient(results=[{"index": 0, "relevance_score": 0.5}])
    reranker = Reranker(model_name="qwen3-rerank", provider="api", client=fake)
    chunks = [FakeChunk(id=1, content="a")]
    reranker.rerank("query", chunks, top_k=10)
    assert fake.post_calls[0][2]["parameters"]["top_n"] == 1


def test_rerank_api_empty_input_no_call() -> None:
    """空输入不发起 API 调用."""
    fake = FakeHttpClient(results=[])
    reranker = Reranker(model_name="qwen3-rerank", provider="api", client=fake)
    assert reranker.rerank("query", [], top_k=5) == []
    assert reranker.rerank("", [FakeChunk(id=1, content="a")], top_k=5) == []
    assert fake.post_calls == []
