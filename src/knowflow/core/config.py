"""应用配置 - 基于 pydantic-settings, 环境变量前缀 KNOWFLOW_."""

from functools import lru_cache

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置. 通过 KNOWFLOW_ 前缀的环境变量或 .env 文件加载."""

    model_config = SettingsConfigDict(
        env_prefix="KNOWFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── 应用 ──
    app_name: str = "KnowFlow"
    env: str = "dev"  # dev / test / prod
    debug: bool = True
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # ── PostgreSQL ──
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "knowflow"
    postgres_password: str = "nexus"
    postgres_db: str = "knowflow"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── Milvus ──
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "knowflow_chunks"
    milvus_dim: int = 1024  # bge-m3 向量维度

    # ── MinIO ──
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "knowflow"
    minio_secure: bool = False

    # ── LLM ──
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # ── 检索 ──
    chunk_size: int = 512  # 分块字符数, 默认与 constants.DEFAULT_CHUNK_SIZE 一致
    chunk_overlap: int = 64  # 分块重叠字符数
    retrieval_top_k: int = 10  # 检索返回 top_k
    rrf_k: int = 60  # Reciprocal Rank Fusion 经典参数
    retrieval_cache_ttl_seconds: int = 300  # 检索结果缓存 TTL
    embedding_batch_size: int = 32  # Embedding 批量推理大小
    reranker_top_k: int = 10  # Reranker 精排后截断数

    # ── 上下文工程 ──
    context_budget_tokens: int = 32000
    spill_threshold_tokens: int = 4000
    window_max_turns: int = 20

    # ── 存储与配额 ──
    session_ttl_seconds: int = 3600
    workspace_quota_bytes: int = 104857600  # 100MB

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn(self) -> str:
        """异步 PG 连接串(asyncpg 驱动)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_test(self) -> bool:
        """是否为测试环境."""
        return self.env == "test"

    @property
    def is_prod(self) -> bool:
        """是否为生产环境."""
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    """获取 Settings 单例. 测试中可通过 get_settings.cache_clear() 重置."""
    return Settings()
