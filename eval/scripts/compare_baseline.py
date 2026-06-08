"""compare_baseline.py - Hybrid vs GraphRAG 检索效果对比.

静态模式(默认): 不依赖真实 LLM/Milvus/Redis, 用 fake 组件 + SQLite 跑通全链路,
    生成对比报告模板. GraphRAG 的提升来自一跳扩展(跨文档实体链接 + 真实 graph_store + expander).
真实模式: 需要 PG/Milvus/Redis/MinIO + LLM API Key, 按 docs/tests/指标测试-检索.md 执行.

用法:
    uv run python eval/scripts/compare_baseline.py              # 静态模式(默认)
    uv run python eval/scripts/compare_baseline.py --mode real  # 真实模式(需外部依赖)
    uv run python eval/scripts/compare_baseline.py --top-k 10   # 指定 top_k
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# 将 src 加入 sys.path, 支持 `python eval/scripts/compare_baseline.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# 评测专用小分块: 合成语料仅 ~4500 字, 默认 chunk_size=512 仅产出 ~10 块,
# top_k=10 时几乎返回全部 chunk, 召回率必然 100% 无区分度.
# 用 chunk_size=128 产出 ~40 块, top_k=10 仅返回 25%, 使检索对比有意义.
os.environ.setdefault("KNOWFLOW_CHUNK_SIZE", "128")
os.environ.setdefault("KNOWFLOW_CHUNK_OVERLAP", "16")

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from knowflow.db.repositories.document_repo import (
    ChunkRepo,
    DocumentIndexRepo,
    DocumentRepo,
)
from knowflow.models import Base
from knowflow.models.graph import Entity, Relation
from knowflow.retrieval.bm25_store import BM25Store, tokenize
from knowflow.retrieval.entity_extractor import (
    Entity as ExtEntity,
)
from knowflow.retrieval.entity_extractor import (
    ExtractResult,
)
from knowflow.retrieval.expander import Expander
from knowflow.retrieval.graph_store import GraphStore
from knowflow.retrieval.hybrid_search import ChunkScore, HybridSearch
from knowflow.retrieval.pipeline import IndexDeps, RetrievalPipeline
from knowflow.retrieval.retriever import GraphRAGRetriever
from knowflow.retrieval.vector_store import ChunkVector, VectorHit

# ── 路径常量 ──

CORPUS_DIR = ROOT / "eval" / "datasets" / "corpus"
EVAL_FILE = ROOT / "eval" / "datasets" / "retrieval_eval.jsonl"
REPORT_DIR = ROOT / "eval" / "reports"
CHUNK_MAP_FILE = ROOT / "eval" / "datasets" / "chunk_id_map.json"
EVAL_DB = ROOT / "eval" / "datasets" / "eval.db"

# Fake embedding 维度
EMBED_DIM = 256

# 已知实体词典(规则抽取用): name -> entity_type
KNOWN_ENTITIES: dict[str, str] = {
    "张三": "person",
    "人力资源部": "org",
    "财务部": "org",
    "IT部": "org",
    "运营部": "org",
    "报销": "process",
    "工单系统": "system",
    "Jira": "system",
    "考勤系统": "system",
    "VPN": "system",
    "入职": "process",
    "离职": "process",
    "KnowFlow": "product",
    "GraphRAG": "product",
    "LangGraph": "product",
    "MinIO": "system",
    "Milvus": "system",
    "Redis": "system",
    "PostgreSQL": "system",
    "FastAPI": "product",
}


# ── Fake 组件(静态模式) ──


class HashingEmbeddingClient:
    """基于 hashing trick 的 fake embedding.

    将 token 通过 md5 哈希到固定维度, 构建归一化向量.
    共享 token 的文本会产生相似向量, 使向量召回有意义.
    """

    def __init__(self, dim: int = EMBED_DIM) -> None:
        self.dim = dim

    def embed_one(self, text: str) -> list[float]:
        """单条文本 embedding."""
        if not text:
            return [0.0] * self.dim
        tokens = tokenize(text)
        vec = [0.0] * self.dim
        for token in tokens:
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量 embedding."""
        return [self.embed_one(t) for t in texts]


class InMemoryVectorStore:
    """内存向量存储, 替代 Milvus. 用点积(IP)计算相似度."""

    def __init__(self) -> None:
        self._vectors: dict[int, list[float]] = {}
        self._doc_ids: dict[int, int] = {}

    def upsert(self, chunks: list[ChunkVector]) -> int:
        """批量写入向量."""
        for c in chunks:
            self._vectors[c.chunk_id] = c.embedding
            self._doc_ids[c.chunk_id] = c.doc_id
        return len(chunks)

    def search(self, query_vector: list[float], top_k: int) -> list[VectorHit]:
        """向量召回: 点积相似度降序取 top_k."""
        if not query_vector or not self._vectors:
            return []
        scored: list[VectorHit] = []
        for chunk_id, vec in self._vectors.items():
            score = sum(a * b for a, b in zip(query_vector, vec, strict=True))
            scored.append(VectorHit(chunk_id=chunk_id, score=score))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def delete_by_doc(self, doc_id: int) -> int:
        """按 doc_id 删除向量."""
        to_del = [cid for cid, did in self._doc_ids.items() if did == doc_id]
        for cid in to_del:
            del self._vectors[cid]
            del self._doc_ids[cid]
        return len(to_del)


class FakeMinio:
    """Fake MinIO, 用内存映射替代文件下载."""

    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def put_object(self, object_name: str, data: bytes) -> None:
        """上传对象."""
        self._objects[object_name] = data

    def fget_object(self, bucket: str, object_name: str, file_path: str) -> Any:
        """下载对象到文件."""
        data = self._objects.get(object_name, b"")
        with open(file_path, "wb") as f:
            f.write(data)
        return None


class RuleBasedEntityExtractor:
    """基于规则的实体抽取器(静态模式用).

    扫描文本中的已知实体名称, 返回 ExtractResult(仅实体, 不含关系).
    跨文档关系由 link_cross_doc_entities 在索引后统一创建.
    """

    def extract(self, chunk_text: str) -> ExtractResult:
        """从文本中抽取已知实体."""
        if not chunk_text:
            return ExtractResult()
        entities: list[ExtEntity] = []
        for name, etype in KNOWN_ENTITIES.items():
            if name in chunk_text:
                entities.append(ExtEntity(name=name, type=etype, normalized=name.lower()))
        return ExtractResult(entities=entities, relations=[])


class TermOverlapReranker:
    """基于查询词项重叠的 fake reranker.

    对 (query, chunk) 对计算词项重叠率作为分数, 按分数降序取 top_k.
    """

    def __init__(self) -> None:
        self._model: Any = None

    def rerank(
        self,
        query: str,
        chunks: list[Any],
        *,
        top_k: int,
    ) -> list[ChunkScore]:
        """对候选 chunk 按 query 词项重叠率重排."""
        if not query or not chunks or top_k <= 0:
            return []
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return [ChunkScore(chunk_id=c.id, score=0.0, source="rerank") for c in chunks[:top_k]]
        scored: list[tuple[float, int]] = []
        for chunk in chunks:
            chunk_tokens = set(tokenize(chunk.content))
            overlap = len(query_tokens & chunk_tokens) / len(query_tokens)
            scored.append((overlap, chunk.id))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            ChunkScore(chunk_id=cid, score=score, source="rerank") for score, cid in scored[:top_k]
        ]


class NoopCache:
    """空缓存(静态模式不缓存, 每次都 miss)."""

    async def get(self, query: str) -> list[ChunkScore] | None:
        return None

    async def set(self, query: str, results: list[ChunkScore]) -> None:
        pass

    async def invalidate(self, query: str) -> None:
        pass


# ── 评测数据结构 ──


@dataclass
class QueryResult:
    """单条查询结果."""

    query: str
    category: str
    relevant_doc_ids: list[int]
    hybrid_chunk_ids: list[int]
    graphrag_chunk_ids: list[int]


@dataclass
class MetricSummary:
    """指标汇总."""

    recall: float
    mrr: float
    count: int


# ── 评测指标 ──


def compute_recall_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int = 10) -> float:
    """Recall@k = |retrieved[:k] ∩ relevant| / |relevant|."""
    if not relevant_ids:
        return 0.0
    retrieved_set = set(retrieved_ids[:k])
    hits = len(retrieved_set & relevant_ids)
    return hits / len(relevant_ids)


def compute_mrr(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    """MRR = 1/rank of first relevant hit (0 if none)."""
    for i, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / i
    return 0.0


def compute_metrics(
    results: list[QueryResult],
    chunk_map: dict[int, list[int]],
    mode: str,
    k: int = 10,
) -> MetricSummary:
    """计算指定模式(hybrid/graphrag)的汇总指标."""
    if not results:
        return MetricSummary(0.0, 0.0, 0)

    total_recall = 0.0
    total_mrr = 0.0
    for r in results:
        relevant_chunks: set[int] = set()
        for did in r.relevant_doc_ids:
            relevant_chunks.update(chunk_map.get(did, []))

        retrieved = r.hybrid_chunk_ids if mode == "hybrid" else r.graphrag_chunk_ids
        total_recall += compute_recall_at_k(retrieved, relevant_chunks, k)
        total_mrr += compute_mrr(retrieved, relevant_chunks)

    n = len(results)
    return MetricSummary(recall=total_recall / n, mrr=total_mrr / n, count=n)


# ── 核心流程 ──


async def setup_database() -> tuple[Any, async_sessionmaker[AsyncSession]]:
    """创建 SQLite 文件库并建表, 返回 (engine, session_factory)."""
    if EVAL_DB.exists():
        EVAL_DB.unlink()

    engine = create_async_engine(f"sqlite+aiosqlite:///{EVAL_DB}", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn: Any, _: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    return engine, factory


async def index_corpus(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[
    dict[int, list[int]],
    dict[str, int],
    InMemoryVectorStore,
    BM25Store,
    HashingEmbeddingClient,
]:
    """索引全部语料, 返回 (chunk_map, doc_title_to_id, vector_store, bm25_store, embedding).

    chunk_map: doc_id -> [chunk_id, ...] (按 chunk_index 升序)
    doc_title_to_id: doc_title -> doc_id
    """
    corpus_files = sorted(CORPUS_DIR.glob("*.md"))
    if not corpus_files:
        raise FileNotFoundError(f"未找到语料文件: {CORPUS_DIR}")

    minio = FakeMinio()
    embedding = HashingEmbeddingClient()
    extractor = RuleBasedEntityExtractor()
    vector_store = InMemoryVectorStore()
    bm25_store = BM25Store()

    chunk_map: dict[int, list[int]] = {}
    doc_title_to_id: dict[str, int] = {}

    for corpus_file in corpus_files:
        content = corpus_file.read_bytes()
        title = corpus_file.stem

        # 上传到 fake MinIO
        source_uri = f"corpus/{corpus_file.name}"
        minio.put_object(source_uri, content)

        # 创建文档记录
        session = factory()
        try:
            doc_repo = DocumentRepo(session)
            doc = await doc_repo.create(
                title=title,
                source_uri=source_uri,
                file_type="md",
                size_bytes=len(content),
            )
            await session.commit()
            doc_id = doc.id
            doc_title_to_id[title] = doc_id
        finally:
            await session.close()

        # 索引
        session = factory()
        try:
            deps = IndexDeps(
                session=session,
                document_repo=DocumentRepo(session),
                chunk_repo=ChunkRepo(session),
                document_index_repo=DocumentIndexRepo(session),
                graph_store=GraphStore(session),
                vector_store=vector_store,  # type: ignore[arg-type]
                bm25_store=bm25_store,  # type: ignore[arg-type]
                embedding_client=embedding,  # type: ignore[arg-type]
                entity_extractor=extractor,  # type: ignore[arg-type]
                minio_client=minio,
                bucket="eval",
            )
            pipeline = RetrievalPipeline(deps)
            result = await pipeline.index_document(doc_id)
            print(
                f"  索引 {title}: "
                f"{result.chunk_count} chunks, "
                f"{result.entity_count} entities, "
                f"{result.relation_count} relations"
            )
        finally:
            await session.close()

        # 收集 chunk_ids
        session = factory()
        try:
            chunk_repo = ChunkRepo(session)
            chunks = await chunk_repo.list_by_doc(doc_id)
            chunk_map[doc_id] = [c.id for c in chunks]
        finally:
            await session.close()

    return chunk_map, doc_title_to_id, vector_store, bm25_store, embedding


async def link_cross_doc_entities(
    factory: async_sessionmaker[AsyncSession],
) -> int:
    """跨文档实体链接: 为同名实体(不同 chunk)创建双向 same_as 关系.

    这是 GraphRAG 的核心: 通过实体名称归一化连接不同文档的 chunk.
    真实场景由 LLM 抽取 + 实体归一化完成, 静态模式用规则模拟.
    """
    session = factory()
    try:
        # 读取全部实体, 按 normalized 名称分组
        result = await session.execute(select(Entity))
        all_entities: list[Entity] = list(result.scalars().all())

        name_to_entities: dict[str, list[Entity]] = {}
        for e in all_entities:
            name_to_entities.setdefault(e.normalized, []).append(e)

        relation_count = 0
        for _name, entities in name_to_entities.items():
            if len(entities) < 2:
                continue
            # 为每对同名实体(不同 chunk)创建双向 same_as 关系
            for i, e1 in enumerate(entities):
                for e2 in entities[i + 1 :]:
                    if e1.chunk_id == e2.chunk_id:
                        continue
                    session.add(
                        Relation(
                            doc_id=e1.doc_id,
                            source_entity_id=e1.id,
                            target_entity_id=e2.id,
                            relation_type="same_as",
                        )
                    )
                    session.add(
                        Relation(
                            doc_id=e2.doc_id,
                            source_entity_id=e2.id,
                            target_entity_id=e1.id,
                            relation_type="same_as",
                        )
                    )
                    relation_count += 2

        await session.commit()
        return relation_count
    finally:
        await session.close()


def load_eval_queries() -> list[dict[str, Any]]:
    """加载评测集."""
    queries: list[dict[str, Any]] = []
    with open(EVAL_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


async def run_evaluation(
    factory: async_sessionmaker[AsyncSession],
    chunk_map: dict[int, list[int]],
    queries: list[dict[str, Any]],
    vector_store: InMemoryVectorStore,
    bm25_store: BM25Store,
    embedding: HashingEmbeddingClient,
    top_k: int,
) -> list[QueryResult]:
    """运行评测, 对每条查询跑 Hybrid 和 GraphRAG 两种模式."""

    hybrid_search = HybridSearch(
        vector_store=vector_store,  # type: ignore[arg-type]
        bm25_store=bm25_store,  # type: ignore[arg-type]
        embedding_client=embedding,  # type: ignore[arg-type]
    )

    # expander 用长生命周期 session
    expander_session = factory()
    expander = Expander(expander_session, graph_store=GraphStore(expander_session))

    reranker = TermOverlapReranker()
    cache = NoopCache()

    retriever = GraphRAGRetriever(
        session_factory=factory,
        hybrid_search=hybrid_search,
        expander=expander,
        reranker=reranker,  # type: ignore[arg-type]
        cache=cache,  # type: ignore[arg-type]
    )

    results: list[QueryResult] = []
    for i, q in enumerate(queries, start=1):
        query = q["query"]
        relevant_doc_ids = q["doc_ids"]
        category = q.get("category", "unknown")

        # Hybrid only
        hybrid_result = await retriever.retrieve(
            query, top_k=top_k, with_expand=False, with_rerank=False
        )
        hybrid_ids = [c.chunk_id for c in hybrid_result.chunks]

        # GraphRAG (expand + rerank)
        graphrag_result = await retriever.retrieve(
            query, top_k=top_k, with_expand=True, with_rerank=True
        )
        graphrag_ids = [c.chunk_id for c in graphrag_result.chunks]

        results.append(
            QueryResult(
                query=query,
                category=category,
                relevant_doc_ids=relevant_doc_ids,
                hybrid_chunk_ids=hybrid_ids,
                graphrag_chunk_ids=graphrag_ids,
            )
        )

        relevant_chunks: set[int] = set()
        for did in relevant_doc_ids:
            relevant_chunks.update(chunk_map.get(did, []))
        h_recall = compute_recall_at_k(hybrid_ids, relevant_chunks, top_k)
        g_recall = compute_recall_at_k(graphrag_ids, relevant_chunks, top_k)
        print(
            f"  [{i:2d}/{len(queries)}] {category:10s} | "
            f"Hybrid R@{top_k}={h_recall:.2f} | "
            f"GraphRAG R@{top_k}={g_recall:.2f} | {query[:30]}"
        )

    await expander_session.close()
    return results


def generate_report(
    results: list[QueryResult],
    chunk_map: dict[int, list[int]],
    doc_title_to_id: dict[str, int],
    top_k: int,
    mode: str,
    cross_doc_relations: int,
) -> str:
    """生成对比报告."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_chunks = sum(len(v) for v in chunk_map.values())

    hybrid_metrics = compute_metrics(results, chunk_map, "hybrid", top_k)
    graphrag_metrics = compute_metrics(results, chunk_map, "graphrag", top_k)

    categories = {"direct": "直接查询", "cross_doc": "跨文档查询", "semantic": "语义查询"}
    group_lines: list[str] = []
    for cat, cat_name in categories.items():
        cat_results = [r for r in results if r.category == cat]
        if not cat_results:
            continue
        h = compute_metrics(cat_results, chunk_map, "hybrid", top_k)
        g = compute_metrics(cat_results, chunk_map, "graphrag", top_k)
        group_lines.append(
            f"| {cat_name} | {h.count} | {h.recall * 100:.1f}% | "
            f"{g.recall * 100:.1f}% | {(g.recall - h.recall) * 100:+.1f}% | "
            f"{h.mrr:.4f} | {g.mrr:.4f} |"
        )

    lines = [
        "# GraphRAG vs Hybrid 检索效果对比报告",
        "",
        f"> 生成时间: {now}",
        f"> 模式: {mode} ({'合成语料 + fake 模型' if mode == 'static' else '真实模型'})",
        f"> 语料: {len(chunk_map)} 篇文档, 共 {total_chunks} 个分块",
        f"> 评测集: {len(results)} 条查询",
        f"> Top-K: {top_k}",
        f"> 跨文档实体链接关系: {cross_doc_relations} 条",
        "",
        "## 文档映射",
        "",
        "| 文档 | doc_id | 分块数 |",
        "|---|---|---|",
    ]
    for title, did in sorted(doc_title_to_id.items(), key=lambda x: x[1]):
        lines.append(f"| {title} | {did} | {len(chunk_map.get(did, []))} |")

    lines.extend(
        [
            "",
            "## 总体指标",
            "",
            "| 指标 | Hybrid | GraphRAG | 提升 |",
            "|---|---|---|---|",
            f"| Recall@{top_k} | {hybrid_metrics.recall * 100:.1f}% | "
            f"{graphrag_metrics.recall * 100:.1f}% | "
            f"{(graphrag_metrics.recall - hybrid_metrics.recall) * 100:+.1f}% |",
            f"| MRR | {hybrid_metrics.mrr:.4f} | "
            f"{graphrag_metrics.mrr:.4f} | "
            f"{graphrag_metrics.mrr - hybrid_metrics.mrr:+.4f} |",
            "",
            "## 分组指标",
            "",
            "| 分组 | 条数 | Hybrid Recall | GraphRAG Recall | 提升 | Hybrid MRR | GraphRAG MRR |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    lines.extend(group_lines)

    lines.extend(
        [
            "",
            "## 逐条结果",
            "",
            f"| # | 查询 | 类别 | Hybrid R@{top_k} | GraphRAG R@{top_k} | "
            "Hybrid MRR | GraphRAG MRR |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for i, r in enumerate(results, start=1):
        relevant_chunks: set[int] = set()
        for did in r.relevant_doc_ids:
            relevant_chunks.update(chunk_map.get(did, []))
        h_r = compute_recall_at_k(r.hybrid_chunk_ids, relevant_chunks, top_k)
        g_r = compute_recall_at_k(r.graphrag_chunk_ids, relevant_chunks, top_k)
        h_mrr = compute_mrr(r.hybrid_chunk_ids, relevant_chunks)
        g_mrr = compute_mrr(r.graphrag_chunk_ids, relevant_chunks)
        lines.append(
            f"| {i} | {r.query} | {r.category} | {h_r:.2f} | {g_r:.2f} | "
            f"{h_mrr:.4f} | {g_mrr:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- **Hybrid**: 向量召回(hashing embedding) + BM25 召回, RRF 融合, 无扩展无精排",
            "- **GraphRAG**: Hybrid + 一跳扩展(跨文档实体链接) + 精排(词项重叠)",
            f"- **Recall@{top_k}**: |检索结果前K ∩ 相关chunk| / |相关chunk|",
            "- **MRR**: 1 / 首个相关结果的排名",
            "- **相关chunk**: 评测集标注的 relevant_doc_ids 对应的全部 chunk",
            "- **跨文档实体链接**: 索引后对同名实体(normalized)创建双向 same_as 关系, "
            "使 one_hop_expand 能从命中 chunk 找到共享实体的其他文档 chunk",
            "",
        ]
    )
    return "\n".join(lines)


async def run_static(top_k: int) -> int:
    """静态模式: 用 fake 组件跑通全链路."""
    print("=" * 60)
    print("GraphRAG vs Hybrid 检索对比 (静态模式)")
    print("=" * 60)

    # 1. 建库
    print("\n[1/5] 初始化 SQLite...")
    engine, factory = await setup_database()

    try:
        # 2. 索引语料
        print("\n[2/5] 索引合成语料...")
        chunk_map, doc_title_to_id, vector_store, bm25_store, embedding = await index_corpus(
            factory
        )

        with open(CHUNK_MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {str(k): v for k, v in chunk_map.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"  chunk_id_map.json 已保存: {CHUNK_MAP_FILE}")
        print(f"  文档映射: {doc_title_to_id}")
        print(f"  总分块数: {sum(len(v) for v in chunk_map.values())}")

        # 3. 跨文档实体链接
        print("\n[3/5] 跨文档实体链接...")
        rel_count = await link_cross_doc_entities(factory)
        print(f"  创建 {rel_count} 条 same_as 关系")

        # 4. 加载评测集并运行
        print(f"\n[4/5] 运行检索对比 (top_k={top_k})...")
        queries = load_eval_queries()
        print(f"  加载 {len(queries)} 条查询")
        results = await run_evaluation(
            factory,
            chunk_map,
            queries,
            vector_store,
            bm25_store,
            embedding,
            top_k,
        )

        # 5. 生成报告
        print("\n[5/5] 生成报告...")
        report = generate_report(results, chunk_map, doc_title_to_id, top_k, "static", rel_count)

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORT_DIR / "compare_20260608.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"  报告已保存: {report_file}")

        # 打印总体指标
        hybrid = compute_metrics(results, chunk_map, "hybrid", top_k)
        graphrag = compute_metrics(results, chunk_map, "graphrag", top_k)
        print("\n" + "=" * 60)
        print("总体指标:")
        print(
            f"  Recall@{top_k}: Hybrid {hybrid.recall * 100:.1f}% | "
            f"GraphRAG {graphrag.recall * 100:.1f}% | "
            f"提升 {(graphrag.recall - hybrid.recall) * 100:+.1f}%"
        )
        print(
            f"  MRR:         Hybrid {hybrid.mrr:.4f} | "
            f"GraphRAG {graphrag.mrr:.4f} | "
            f"提升 {graphrag.mrr - hybrid.mrr:+.4f}"
        )
        print("=" * 60)
        return 0

    finally:
        await engine.dispose()
        # 清理临时 DB
        with contextlib_suppress():
            if EVAL_DB.exists():
                EVAL_DB.unlink()


def run_real() -> int:
    """真实模式: 需要外部依赖, 提示用户按测试文档执行."""
    print("真实模式需要 PG/Milvus/Redis/MinIO + LLM API Key.")
    print("请按 docs/tests/指标测试-检索.md 执行.")
    print()
    print("前置条件:")
    print("  1. docker compose up -d (启动 PG/Milvus/Redis/MinIO)")
    print("  2. uv run python scripts/init_db.py (建表)")
    print("  3. uv run python scripts/init_milvus.py (建 collection)")
    print("  4. 设置 KNOWFLOW_LLM_API_KEY 环境变量")
    print("  5. 下载 bge-m3 与 bge-reranker-v2-m3 模型")
    return 1


def contextlib_suppress() -> Any:
    """contextlib.suppress 包装, 避免顶层 import."""
    import contextlib

    return contextlib.suppress(OSError)


def main() -> int:
    parser = argparse.ArgumentParser(description="GraphRAG vs Hybrid 检索对比")
    parser.add_argument(
        "--mode",
        choices=["static", "real"],
        default="static",
        help="运行模式: static(默认, fake 组件) / real(需外部依赖)",
    )
    parser.add_argument("--top-k", type=int, default=10, help="检索 top_k (默认 10)")
    args = parser.parse_args()

    if args.mode == "real":
        return run_real()
    return asyncio.run(run_static(args.top_k))


if __name__ == "__main__":
    sys.exit(main())
