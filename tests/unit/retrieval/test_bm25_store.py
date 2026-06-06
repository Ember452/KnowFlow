"""bm25_store 单测 - 构建 / 查询 / 增量 / 删除 / 中文 tokenization."""

from knowflow.retrieval.bm25_store import (
    BM25Doc,
    BM25Store,
    dispose_bm25_store,
    get_bm25_store,
    tokenize,
)

# ── tokenize 单测 ──


def test_tokenize_english() -> None:
    """英文按空格切分并小写化."""
    assert tokenize("Hello World") == ["hello", "world"]


def test_tokenize_chinese() -> None:
    """中文按单字符切分."""
    assert tokenize("你好世界") == ["你", "好", "世", "界"]


def test_tokenize_mixed() -> None:
    """中英文混合: 英文按词, 中文按字."""
    tokens = tokenize("Hello 世界")
    assert "hello" in tokens
    assert "世" in tokens
    assert "界" in tokens


def test_tokenize_punctuation() -> None:
    """标点被丢弃, 不作为 token."""
    assert tokenize("hello, world!") == ["hello", "world"]


def test_tokenize_empty() -> None:
    """空字符串返回空列表."""
    assert tokenize("") == []


# ── BM25Store 构建与查询 ──


def test_build_and_search() -> None:
    """构建索引后能命中相关文档."""
    corpus = [
        BM25Doc(chunk_id=1, content="Python is a programming language", doc_id=10),
        BM25Doc(chunk_id=2, content="Java is also a programming language", doc_id=10),
        BM25Doc(chunk_id=3, content="The weather is nice today", doc_id=11),
    ]
    store = BM25Store(corpus)
    assert store.size == 3

    hits = store.search("Python programming", top_k=2)
    assert len(hits) <= 2
    # chunk 1 应排第一(Python 出现)
    assert hits[0].chunk_id == 1
    assert hits[0].score > 0


def test_search_empty_query() -> None:
    """空查询返回空列表."""
    store = BM25Store([BM25Doc(chunk_id=1, content="hello", doc_id=1)])
    assert store.search("", top_k=5) == []


def test_search_empty_index() -> None:
    """空索引查询返回空列表."""
    store = BM25Store()
    assert store.search("anything", top_k=5) == []


def test_search_no_match() -> None:
    """查询无匹配 token 时返回空列表(零分被过滤)."""
    store = BM25Store([BM25Doc(chunk_id=1, content="apple banana", doc_id=1)])
    hits = store.search("zebra", top_k=5)
    assert hits == []


def test_search_chinese() -> None:
    """中文查询能命中."""
    corpus = [
        BM25Doc(chunk_id=1, content="张三在财务部工作", doc_id=10),
        BM25Doc(chunk_id=2, content="李四在技术部工作", doc_id=11),
    ]
    store = BM25Store(corpus)
    hits = store.search("张三", top_k=2)
    assert len(hits) >= 1
    assert hits[0].chunk_id == 1


# ── 增量追加 ──


def test_add_single() -> None:
    """add 单个文档后能查到."""
    store = BM25Store()
    store.add(BM25Doc(chunk_id=1, content="hello world", doc_id=1))
    assert store.size == 1
    hits = store.search("hello", top_k=5)
    assert len(hits) == 1
    assert hits[0].chunk_id == 1


def test_add_batch() -> None:
    """add_batch 批量追加."""
    store = BM25Store()
    docs = [
        BM25Doc(chunk_id=1, content="apple", doc_id=1),
        BM25Doc(chunk_id=2, content="banana", doc_id=1),
        BM25Doc(chunk_id=3, content="cherry", doc_id=2),
    ]
    store.add_batch(docs)
    assert store.size == 3
    hits = store.search("banana", top_k=5)
    assert hits[0].chunk_id == 2


def test_add_then_search_new_doc() -> None:
    """增量追加后能查到新文档."""
    store = BM25Store([BM25Doc(chunk_id=1, content="apple", doc_id=1)])
    store.add(BM25Doc(chunk_id=2, content="banana", doc_id=1))
    hits = store.search("banana", top_k=5)
    assert len(hits) == 1
    assert hits[0].chunk_id == 2


# ── 删除 ──


def test_delete_by_doc() -> None:
    """按 doc_id 删除文档."""
    store = BM25Store(
        [
            BM25Doc(chunk_id=1, content="apple", doc_id=10),
            BM25Doc(chunk_id=2, content="banana", doc_id=10),
            BM25Doc(chunk_id=3, content="cherry", doc_id=11),
        ]
    )
    deleted = store.delete_by_doc(10)
    assert deleted == 2
    assert store.size == 1
    # 剩余的是 doc_id=11 的 cherry
    hits = store.search("cherry", top_k=5)
    assert len(hits) == 1
    assert hits[0].chunk_id == 3
    # apple 已被删除
    assert store.search("apple", top_k=5) == []


def test_delete_nonexistent_doc() -> None:
    """删除不存在的 doc_id 返回 0, 不报错."""
    store = BM25Store([BM25Doc(chunk_id=1, content="apple", doc_id=10)])
    deleted = store.delete_by_doc(999)
    assert deleted == 0
    assert store.size == 1


# ── 单例管理 ──


def test_get_bm25_store_singleton() -> None:
    """get_bm25_store 返回缓存单例."""
    dispose_bm25_store()
    from knowflow.retrieval import bm25_store as mod

    fake_store = BM25Store()
    mod._bm25_store = fake_store
    s1 = get_bm25_store()
    s2 = get_bm25_store()
    assert s1 is s2 is fake_store
    dispose_bm25_store()
    assert mod._bm25_store is None


# ── top_k 边界 ──


def test_search_top_k_zero() -> None:
    """top_k <= 0 返回空列表."""
    store = BM25Store([BM25Doc(chunk_id=1, content="hello", doc_id=1)])
    assert store.search("hello", top_k=0) == []


def test_search_top_k_exceeds_size() -> None:
    """top_k 超过索引大小时返回全部命中."""
    store = BM25Store([BM25Doc(chunk_id=1, content="hello", doc_id=1)])
    hits = store.search("hello", top_k=100)
    assert len(hits) == 1
