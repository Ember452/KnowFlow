"""Reranker - cross-encoder 精排, 对 (query, chunk) 对打分后重排.

基于 sentence-transformers CrossEncoder, 进程内单例.
单测通过构造时注入 fake model 绕过真实模型加载.
"""

from collections.abc import Sequence
from typing import Any

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger
from knowflow.retrieval.hybrid_search import ChunkScore

logger = get_logger(__name__)

_reranker: "Reranker | None" = None


class Reranker:
    """Cross-encoder 精排器."""

    def __init__(self, model: Any | None = None, *, model_name: str | None = None) -> None:
        """初始化.

        Args:
            model: 已加载的 CrossEncoder 实例(单测注入 fake 用).
            model_name: 模型名, 默认取 settings.reranker_model.
        """
        if model is not None:
            self._model: Any = model
        else:
            # 延迟导入: 避免模块加载时拉起 torch
            from sentence_transformers import CrossEncoder

            name = model_name or get_settings().reranker_model
            logger.info("reranker.loading", model=name)
            self._model = CrossEncoder(name)
            logger.info("reranker.loaded", model=name)

    def rerank(
        self,
        query: str,
        chunks: Sequence[Any],  # Chunk ORM 或含 content 属性的对象
        *,
        top_k: int,
    ) -> list[ChunkScore]:
        """对 (query, chunk.content) 对打分, 按分数降序取 top_k.

        Args:
            query: 查询文本.
            chunks: 待精排的 chunk 列表(需有 id 与 content 属性).
            top_k: 返回条数.

        Returns:
            ChunkScore 列表, source="rerank".
        """
        if not query or not chunks or top_k <= 0:
            return []

        # 构造 (query, content) 对
        pairs = [(query, c.content) for c in chunks]
        scores = self._model.predict(pairs)

        # 配对 chunk_id 与分数, 按分数降序取 top_k
        paired: list[tuple[float, int]] = []
        for chunk, score in zip(chunks, scores, strict=True):
            paired.append((float(score), chunk.id))
        paired.sort(key=lambda x: x[0], reverse=True)

        return [
            ChunkScore(chunk_id=cid, score=score, source="rerank") for score, cid in paired[:top_k]
        ]


def get_reranker() -> Reranker:
    """获取进程内单例 Reranker. 单测可 monkeypatch 替换."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def dispose_reranker() -> None:
    """释放单例(便于单测 reset 与应用关闭)."""
    global _reranker
    _reranker = None
