"""Settings 配置加载单测. 用 _env_file=None 隔离 .env 文件影响."""

from knowflow.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    """不传参时应使用默认值."""
    s = Settings(_env_file=None)
    assert s.app_name == "KnowFlow"
    assert s.env == "dev"
    assert s.debug is True
    assert s.api_prefix == "/api/v1"
    assert s.context_budget_tokens == 32000


def test_postgres_dsn_format() -> None:
    """postgres_dsn 应拼接为 asyncpg 异步连接串."""
    s = Settings(
        _env_file=None,
        postgres_host="db.host",
        postgres_port=6543,
        postgres_user="u",
        postgres_password="p@ss",
        postgres_db="mydb",
    )
    assert s.postgres_dsn == "postgresql+asyncpg://u:p@ss@db.host:6543/mydb"


def test_env_flags() -> None:
    """is_test / is_prod 应根据 env 字段切换."""
    test_s = Settings(_env_file=None, env="test")
    assert test_s.is_test is True
    assert test_s.is_prod is False

    prod_s = Settings(_env_file=None, env="prod")
    assert prod_s.is_test is False
    assert prod_s.is_prod is True


def test_get_settings_singleton() -> None:
    """get_settings 应返回缓存的单例."""
    get_settings.cache_clear()
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
    get_settings.cache_clear()


def test_minio_secure_bool() -> None:
    """minio_secure 应正确解析为 bool."""
    s = Settings(_env_file=None, minio_secure=True)
    assert s.minio_secure is True


def test_retrieval_defaults() -> None:
    """检索参数应有默认值且与 constants 对齐."""
    from knowflow.core.constants import (
        DEFAULT_CHUNK_OVERLAP,
        DEFAULT_CHUNK_SIZE,
        DEFAULT_TOP_K,
        RRF_K,
    )

    s = Settings(_env_file=None)
    assert s.chunk_size == DEFAULT_CHUNK_SIZE == 512
    assert s.chunk_overlap == DEFAULT_CHUNK_OVERLAP == 64
    assert s.retrieval_top_k == DEFAULT_TOP_K == 10
    assert s.rrf_k == RRF_K == 60
    assert s.retrieval_cache_ttl_seconds == 300
    assert s.embedding_batch_size == 32
    assert s.reranker_top_k == 10
