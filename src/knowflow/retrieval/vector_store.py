"""Milvus 向量存储 - 封装 upsert/search/delete, collection 由 init_milvus.py 建.

Collection schema(见 scripts/init_milvus.py):
    id (INT64, primary key) = chunk_id
    doc_id (INT64)
    embedding (FLOAT_VECTOR, dim=1024)
    索引: HNSW (M=16, efConstruction=200), 度量 IP
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ChunkVector:
    """待写入 Milvus 的向量数据."""

    chunk_id: int
    doc_id: int
    embedding: list[float]


@dataclass(frozen=True)
class VectorHit:
    """向量召回结果."""

    chunk_id: int
    score: float


class VectorStore:
    """Milvus 向量存储客户端封装."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        collection_name: str | None = None,
    ) -> None:
        """初始化.

        Args:
            client: MilvusClient 实例. None 时调 get_milvus() 取单例.
            collection_name: collection 名, None 时取 settings.milvus_collection.
        """
        if client is not None:
            self._client: Any = client
        else:
            # 延迟导入避免模块加载时连 Milvus
            from knowflow.db.milvus import get_milvus

            self._client = get_milvus()

        if collection_name is not None:
            self._collection = collection_name
        else:
            from knowflow.core.config import get_settings

            self._collection = get_settings().milvus_collection

    def upsert(self, chunks: Sequence[ChunkVector]) -> int:
        """批量 upsert 向量.

        Args:
            chunks: 待写入的向量数据列表.

        Returns:
            写入条数.
        """
        if not chunks:
            return 0
        data = [{"id": c.chunk_id, "doc_id": c.doc_id, "embedding": c.embedding} for c in chunks]
        self._client.upsert(collection_name=self._collection, data=data)
        logger.info("vector_store.upserted", count=len(data))
        return len(data)

    def search(self, query_vector: list[float], top_k: int) -> list[VectorHit]:
        """向量召回.

        Args:
            query_vector: 查询向量.
            top_k: 返回条数.

        Returns:
            VectorHit 列表, 按分数降序.
        """
        if not query_vector:
            return []
        results = self._client.search(
            collection_name=self._collection,
            data=[query_vector],
            limit=top_k,
            search_params={"metric_type": "IP", "params": {"ef": 64}},
            output_fields=["id"],
        )
        # Milvus 返回 [[{id, distance, entity}]], 取第一组
        hits: list[VectorHit] = []
        if not results:
            return hits
        for hit in results[0]:
            if isinstance(hit, dict):
                chunk_id_raw = hit.get("id")
                score_raw = hit.get("distance", 0.0)
            else:
                chunk_id_raw = getattr(hit, "id", None)
                score_raw = getattr(hit, "distance", 0.0)
            if chunk_id_raw is None:
                continue
            hits.append(VectorHit(chunk_id=int(chunk_id_raw), score=float(score_raw)))
        return hits

    def delete_by_doc(self, doc_id: int) -> int:
        """按 doc_id 删除向量(重建索引时清理).

        Args:
            doc_id: 文档 id.

        Returns:
            删除条数(Milvus 不返回精确数, 此处返回 0 仅作占位).
        """
        self._client.delete(
            collection_name=self._collection,
            filter=f"doc_id == {doc_id}",
        )
        logger.info("vector_store.deleted_by_doc", doc_id=doc_id)
        return 0
