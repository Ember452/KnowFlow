"""Embedding 客户端封装 - 基于 sentence-transformers, 进程内单例.

对外暴露 EmbeddingClient 类与 get_embedding_client() 懒加载入口.
单测通过 monkeypatch 替换 _embedding_client 或直接构造 EmbeddingClient
传 model 参数, 避免加载真实模型.
"""

from collections.abc import Sequence
from typing import Any

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_embedding_client: "EmbeddingClient | None" = None


class EmbeddingClient:
    """Embedding 推理客户端.

    两种后端(provider):
    - api: 阿里云百炼 OpenAI 兼容 /embeddings 接口(默认, 免本地模型)
    - local: SentenceTransformer 本地模型
    按 embedding_batch_size 分批推理, 避免超限/显存爆.
    单测可构造时传入 fake model(实现 encode/embed_documents)绕过真实加载.
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        batch_size: int | None = None,
        model: Any | None = None,
        provider: str | None = None,
    ) -> None:
        """初始化.

        Args:
            model_name: 模型名, 默认取 settings.embedding_model.
            batch_size: 批量推理大小, 默认取 settings.embedding_batch_size.
            model: 已加载的模型实例(单测注入 fake 用), 传入时跳过真实加载;
                未显式传 provider 时按本地 encode 接口调用.
            provider: "api"(百炼) / "local"; 默认取 settings.embedding_provider.
        """
        settings = get_settings()
        self.model_name = model_name or settings.embedding_model
        self.batch_size = batch_size or settings.embedding_batch_size

        if model is not None:
            # 单测注入 fake model, 跳过真实加载; 默认按本地 encode 接口调用
            self._model: Any = model
            self.provider = provider or "local"
        else:
            self.provider = provider or settings.embedding_provider
            if self.provider == "api":
                # 阿里云百炼: OpenAI 兼容 /embeddings(text-embedding-v3/v4 默认 1024 维)
                from langchain_openai import OpenAIEmbeddings
                from pydantic import SecretStr

                logger.info("embedding.api_init", model=self.model_name)
                self._model = OpenAIEmbeddings(
                    model=self.model_name,
                    api_key=SecretStr(settings.embedding_api_key),
                    base_url=settings.embedding_base_url,
                )
            else:
                # 延迟导入: 避免模块加载时拉起 torch
                from sentence_transformers import SentenceTransformer

                logger.info("embedding.loading", model=self.model_name)
                self._model = SentenceTransformer(self.model_name)
                logger.info("embedding.loaded", model=self.model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """批量 embedding.

        按 batch_size 切片推理, 拼接返回. 空输入返回空列表.

        Args:
            texts: 待 embedding 的文本列表.

        Returns:
            向量列表, 每个向量维度由模型决定(百炼 text-embedding-v4 默认 1024).
        """
        if not texts:
            return []

        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = list(texts[i : i + self.batch_size])
            if self.provider == "api":
                # OpenAIEmbeddings.embed_documents 返回 list[list[float]]
                vecs = self._model.embed_documents(batch)
            else:
                # SentenceTransformer.encode 返回 np.ndarray, 转成 list[list[float]]
                vecs = self._model.encode(batch)
            # 兼容 fake model 返回 list[list[float]] 或 np.ndarray
            for v in vecs:
                results.append([float(x) for x in v])
        return results

    def embed_one(self, text: str) -> list[float]:
        """单条文本 embedding 便利方法."""
        if not text:
            return []
        vecs = self.embed([text])
        return vecs[0] if vecs else []


def get_embedding_client() -> EmbeddingClient:
    """获取进程内单例 EmbeddingClient. 单测可 monkeypatch 替换."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def dispose_embedding_client() -> None:
    """释放单例(便于单测 reset 与应用关闭)."""
    global _embedding_client
    _embedding_client = None
