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
    """Cross-encoder 精排器, 对 (query, chunk) 对打分后重排.

    两种后端(provider):
    - api: 阿里云百炼 qwen3-rerank(DashScope 原生 rerank API, 默认, 免本地模型)
    - local: sentence-transformers CrossEncoder 本地模型
    单测构造时注入 fake model 或 fake http client 绕过真实调用.
    """

    def __init__(
        self,
        model: Any | None = None,
        *,
        model_name: str | None = None,
        provider: str | None = None,
        client: Any | None = None,
    ) -> None:
        """初始化.

        Args:
            model: 已加载的 CrossEncoder 实例(单测注入 fake 用); 注入时未显式
                传 provider 则按本地 predict 接口调用.
            model_name: 模型名, 默认取 settings.reranker_model.
            provider: "api"(百炼) / "local"; 默认取 settings.reranker_provider.
            client: 注入的 httpx.Client(单测 fake 用), 仅 api 后端使用.
        """
        settings = get_settings()
        self.model_name = model_name or settings.reranker_model
        if model is not None:
            self._model: Any = model
            self.provider = provider or "local"
            self._client = client
        else:
            self.provider = provider or settings.reranker_provider
            if self.provider == "api":
                import httpx

                logger.info("reranker.api_init", model=self.model_name)
                self._model = None
                self._client = client or httpx.Client(timeout=60)
                self._api_url = settings.reranker_api_url
                self._api_key = settings.reranker_api_key
            else:
                # 延迟导入: 避免模块加载时拉起 torch
                from sentence_transformers import CrossEncoder

                logger.info("reranker.loading", model=self.model_name)
                self._model = CrossEncoder(self.model_name)
                self._client = None
                logger.info("reranker.loaded", model=self.model_name)

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

        if self.provider == "api":
            return self._rerank_api(query, chunks, top_k)

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

    def _rerank_api(self, query: str, chunks: Sequence[Any], top_k: int) -> list[ChunkScore]:
        """百炼 qwen3-rerank: DashScope 原生 rerank API(非 OpenAI 兼容).

        POST {reranker_api_url}, 请求 {model, input{query, documents}, parameters{top_n}},
        响应 output.results[{index, relevance_score}](按分数降序).
        """
        assert self._client is not None  # api provider 下必有 http client
        documents = [c.content for c in chunks]
        resp = self._client.post(
            self._api_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self.model_name,
                "input": {"query": query, "documents": documents},
                "parameters": {"top_n": min(top_k, len(chunks))},
            },
        )
        resp.raise_for_status()
        results = resp.json().get("output", {}).get("results", [])
        return [
            ChunkScore(
                chunk_id=chunks[int(item["index"])].id,
                score=float(item.get("relevance_score", 0.0)),
                source="rerank",
            )
            for item in results
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
