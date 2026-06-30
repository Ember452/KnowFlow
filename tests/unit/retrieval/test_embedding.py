"""embedding 单测 - mock SentenceTransformer, 验证批量分批 / 维度 / 单条与批量一致性."""

from knowflow.retrieval.embedding import (
    EmbeddingClient,
    dispose_embedding_client,
    get_embedding_client,
)


class FakeModel:
    """fake 模型: 每条文本返回固定维度(8)的向量, 向量值按文本 hash 生成可复现."""

    dim = 8

    def encode(self, texts: list[str]) -> list[list[float]]:
        """返回与文本长度成比例的固定向量, 便于断言."""
        return [[float(len(t)) * 0.1 + i * 0.01 for i in range(self.dim)] for t in texts]


def test_embed_empty() -> None:
    """空输入返回空列表."""
    client = EmbeddingClient(model=FakeModel(), batch_size=4)
    assert client.embed([]) == []


def test_embed_one_returns_vector() -> None:
    """embed_one 返回非空向量(空字符串返回空列表)."""
    client = EmbeddingClient(model=FakeModel(), batch_size=4)
    vec = client.embed_one("hello")
    assert len(vec) == FakeModel.dim
    # 空字符串应返回空列表(embed 内部短路)
    assert client.embed_one("") == []


def test_embed_batch_split() -> None:
    """批量超过 batch_size 时应自动分批, 结果拼接一致."""
    fake = FakeModel()
    client = EmbeddingClient(model=fake, batch_size=3)
    # 不同长度文本, fake model 按长度生成不同向量
    texts = ["a" * (i + 1) for i in range(10)]  # 长度 1..10, batch_size=3 -> 4 批
    vecs = client.embed(texts)
    assert len(vecs) == 10
    # 每条向量维度正确
    assert all(len(v) == FakeModel.dim for v in vecs)
    # 第 0 条(长度1)与第 9 条(长度10)向量值应不同
    assert vecs[0] != vecs[9]


def test_embed_single_batch_no_split() -> None:
    """批量 <= batch_size 时不分批, 一次推理."""
    fake = FakeModel()
    client = EmbeddingClient(model=fake, batch_size=32)
    texts = ["a", "bb", "ccc"]
    vecs = client.embed(texts)
    assert len(vecs) == 3
    # fake 模型按文本长度生成向量, 三条长度不同, 向量不同
    assert vecs[0] != vecs[1] != vecs[2]


def test_embed_one_consistent_with_embed() -> None:
    """embed_one(text) 与 embed([text])[0] 结果一致."""
    fake = FakeModel()
    client = EmbeddingClient(model=fake, batch_size=4)
    single = client.embed_one("hello world")
    batch = client.embed(["hello world"])
    assert single == batch[0]


def test_get_embedding_client_singleton() -> None:
    """get_embedding_client 应返回缓存单例."""
    dispose_embedding_client()

    # 手动构造一个 client 并注入为单例
    from knowflow.retrieval import embedding as emb_mod

    fake_client = EmbeddingClient(model=FakeModel(), batch_size=4)
    emb_mod._embedding_client = fake_client

    c1 = get_embedding_client()
    c2 = get_embedding_client()
    assert c1 is c2 is fake_client

    dispose_embedding_client()
    assert emb_mod._embedding_client is None


def test_init_with_custom_model_name_and_batch() -> None:
    """构造时显式传 model_name/batch_size 应覆盖默认值."""
    client = EmbeddingClient(
        model_name="fake-model",
        batch_size=2,
        model=FakeModel(),
    )
    assert client.model_name == "fake-model"
    assert client.batch_size == 2


class FakeApiModel:
    """fake 百炼 OpenAIEmbeddings: 实现 embed_documents 接口."""

    dim = 8

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """返回与文本长度成比例的固定向量, 便于断言."""
        return [[float(len(t)) * 0.2 + i * 0.01 for i in range(self.dim)] for t in texts]


def test_embed_api_provider_uses_embed_documents() -> None:
    """api provider 走 embed_documents 接口(百炼 OpenAI 兼容)."""
    fake = FakeApiModel()
    client = EmbeddingClient(model=fake, batch_size=4, provider="api")
    assert client.provider == "api"
    vecs = client.embed(["hello", "world"])
    assert len(vecs) == 2
    assert all(len(v) == FakeApiModel.dim for v in vecs)


def test_embed_injected_model_defaults_local() -> None:
    """注入 model 未传 provider 时按本地 encode 接口调用(向后兼容)."""
    client = EmbeddingClient(model=FakeModel(), batch_size=4)
    assert client.provider == "local"
    vecs = client.embed(["a", "bb"])
    assert len(vecs) == 2
