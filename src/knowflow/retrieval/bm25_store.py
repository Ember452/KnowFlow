"""BM25 内存索引 - 基于 rank-bm25, 进程内单例.

设计文档 3.4 写 "PostgreSQL tsvector", 本实现取 rank-bm25 等价:
- 依赖已在 pyproject 声明, 单测可直接跑
- 不依赖 PG 容器, 启动时由 init_bm25_store 从 chunks 表全量重建
- 如生产需要 PG tsvector, 仅需替换本文件, 调用方接口不变

tokenize 策略: 中英文混合 - 英文按空格分词(小写化), 中文按单字符切分.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from knowflow.core.logging import get_logger
from knowflow.models.document import Chunk

logger = get_logger(__name__)

# 中文字符范围(基本区 + 扩展A), 用于区分中英文 tokenization
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


@dataclass
class BM25Doc:
    """BM25 索引文档."""

    chunk_id: int
    content: str
    doc_id: int


@dataclass(frozen=True)
class BM25Hit:
    """BM25 召回结果."""

    chunk_id: int
    score: float


@dataclass
class _IndexEntry:
    """索引内部条目, 保存 token 与元数据."""

    chunk_id: int
    doc_id: int
    tokens: list[str]


def tokenize(text: str) -> list[str]:
    """中英文混合分词.

    英文: 按空格/标点切分, 小写化.
    中文: 按单字符切分(简单且无需 jieba 依赖).

    Args:
        text: 原始文本.

    Returns:
        token 列表.
    """
    if not text:
        return []
    tokens: list[str] = []
    # 按非字母数字(含中文字符)分段处理
    # 中文逐字, 英文按空格切分后小写
    buf = ""
    for ch in text:
        if _CJK_RE.match(ch):
            # 中文: 先 flush 英文 buf, 再加单字
            if buf:
                tokens.extend(buf.lower().split())
                buf = ""
            tokens.append(ch)
        elif ch.isalnum():
            buf += ch
        else:
            # 非字母数字(空格/标点): flush buf
            if buf:
                tokens.extend(buf.lower().split())
                buf = ""
    if buf:
        tokens.extend(buf.lower().split())
    return tokens


class BM25Store:
    """BM25 内存索引. 启动时从 chunks 全量重建, 索引时增量追加.

    增量追加通过重建内部 BM25Okapi 实现(corpus 量级小可接受).
    """

    def __init__(self, corpus: Sequence[BM25Doc] | None = None) -> None:
        """初始化, 可选传入初始语料.

        Args:
            corpus: 初始语料列表, 启动时从 chunks 表全量重建用.
        """
        self._entries: list[_IndexEntry] = []
        self._bm25: BM25Okapi | None = None
        if corpus:
            self.rebuild(corpus)

    def rebuild(self, corpus: Sequence[BM25Doc]) -> None:
        """全量重建索引(启动加载/重置用, 覆盖现有语料)."""
        self._entries = [
            _IndexEntry(
                chunk_id=d.chunk_id,
                doc_id=d.doc_id,
                tokens=tokenize(d.content),
            )
            for d in corpus
        ]
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """重建 BM25Okapi 索引."""
        if not self._entries:
            self._bm25 = None
            return
        corpus_tokens = [e.tokens for e in self._entries]
        self._bm25 = BM25Okapi(corpus_tokens)

    def add(self, doc: BM25Doc) -> None:
        """增量追加单个文档(重建内部索引)."""
        self._entries.append(
            _IndexEntry(
                chunk_id=doc.chunk_id,
                doc_id=doc.doc_id,
                tokens=tokenize(doc.content),
            )
        )
        self._rebuild_index()

    def add_batch(self, docs: Sequence[BM25Doc]) -> None:
        """批量追加文档."""
        for d in docs:
            self._entries.append(
                _IndexEntry(
                    chunk_id=d.chunk_id,
                    doc_id=d.doc_id,
                    tokens=tokenize(d.content),
                )
            )
        self._rebuild_index()

    def search(self, query: str, top_k: int) -> list[BM25Hit]:
        """BM25 召回.

        Args:
            query: 查询文本.
            top_k: 返回条数.

        Returns:
            BM25Hit 列表, 按分数降序.
        """
        if not query or self._bm25 is None or top_k <= 0:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        query_token_set = set(query_tokens)
        scores = self._bm25.get_scores(query_tokens)
        # 配对并过滤: 仅保留与查询有 token 交集的文档
        # (小语料下 BM25 分数可能为负或 0, 不能用 score > 0 判断是否有匹配)
        paired: list[tuple[float, _IndexEntry]] = []
        for score, entry in zip(scores, self._entries, strict=True):
            if query_token_set & set(entry.tokens):
                paired.append((float(score), entry))
        paired.sort(key=lambda x: x[0], reverse=True)
        return [BM25Hit(chunk_id=e.chunk_id, score=s) for s, e in paired[:top_k]]

    def delete_by_doc(self, doc_id: int) -> int:
        """按 doc_id 删除文档(过滤后重建).

        Returns:
            删除条数.
        """
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.doc_id != doc_id]
        deleted = before - len(self._entries)
        if deleted > 0:
            self._rebuild_index()
        return deleted

    @property
    def size(self) -> int:
        """当前索引文档数."""
        return len(self._entries)

    @property
    def entries(self) -> list[_IndexEntry]:
        """内部条目(仅用于测试断言)."""
        return self._entries


# ── 进程内单例管理 ──

_bm25_store: BM25Store | None = None


async def init_bm25_store(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """启动时从 chunks 表全量加载 BM25 索引到进程内单例.

    幂等: 可重复调用, 每次以 DB 全量为准重建. API 与 Worker 进程各自调用,
    各自持有同源索引(进程内增量写入不跨进程同步, 重启后恢复一致).

    Args:
        session_factory: 已初始化的 session factory.
    """
    global _bm25_store
    async with session_factory() as session:
        result = await session.execute(select(Chunk.id, Chunk.content, Chunk.doc_id))
        rows = result.all()
    corpus = [BM25Doc(chunk_id=cid, content=content, doc_id=did) for cid, content, did in rows]
    if _bm25_store is None:
        _bm25_store = BM25Store()
    _bm25_store.rebuild(corpus)
    logger.info("bm25.index_loaded", chunk_count=len(corpus))


def get_bm25_store() -> BM25Store:
    """获取进程内单例 BM25Store. 单测可 monkeypatch 替换."""
    global _bm25_store
    if _bm25_store is None:
        _bm25_store = BM25Store()
    return _bm25_store


def dispose_bm25_store() -> None:
    """释放单例(便于单测 reset 与应用关闭)."""
    global _bm25_store
    _bm25_store = None
