"""应用配置 - 基于 pydantic-settings, 环境变量前缀 KNOWFLOW_."""

from functools import lru_cache
from typing import Any

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
    # socket 读取超时秒数; 须大于 task_block_ms(阻塞读期间会命中该超时), 过小会误杀 XREADGROUP
    redis_socket_timeout: float = 10.0

    # ── Milvus ──
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "knowflow_chunks"
    milvus_dim: int = 1024  # 向量维度(qwen3.7-text-embedding 默认 1024)

    # ── MinIO ──
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "knowflow"
    minio_secure: bool = False

    # ── LLM ──
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-v4-flash"

    # ── Embedding(api=阿里云百炼 / local=sentence-transformers 本地) ──
    embedding_provider: str = "api"
    embedding_model: str = "qwen3.7-text-embedding"
    embedding_api_key: str = ""  # 百炼 API Key(与 LLM Key 独立)
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ── Reranker(api=阿里云百炼 / local=cross-encoder 本地) ──
    reranker_provider: str = "api"
    reranker_model: str = "qwen3-rerank"
    reranker_api_key: str = ""  # 百炼 API Key
    reranker_api_url: str = (
        "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
    )

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

    # ── 记忆 ──
    memory_recall_top_k: int = 3  # 记忆召回条数
    memory_sediment_interval: int = 5  # 每 N 轮对话沉淀短期记忆入长期
    memory_sediment_threshold: float = 6.0  # 沉淀的重要性阈值(0-10)
    memory_dedup_threshold: float = 0.9  # 去重: 与已有记忆相似度达该值视为重复, 覆盖更新

    # ── 存储与配额 ──
    session_ttl_seconds: int = 3600
    workspace_quota_bytes: int = 104857600  # 100MB

    # ── 工具治理 ──
    skills_dir: str = "skills"  # Skill 声明式定义目录(SKILL.md)
    max_tool_rounds: int = 5  # 工具调用最大轮数
    # MCP Server 接入列表, 每项: {"id": "demo", "command": "python",
    # "args": ["-m", "knowflow.tools.mcp.servers.demo"], "domain": "skill_only"}
    # 启动时经 register_mcp_server 注册进工具注册表(单个不可用降级, 不阻塞启动)
    mcp_servers: list[dict[str, Any]] = []

    # ── API 与上传 ──
    cors_origins: str = "*"  # 逗号分隔; dev 放开, prod 收紧
    rate_limit_per_minute: int = 60  # 每 IP 每分钟请求上限
    upload_max_bytes: int = 52428800  # 50MB
    upload_allowed_types: str = "pdf,docx,md,txt"  # 逗号分隔

    # ── 任务队列 (Redis Stream) ──
    task_stream_index: str = "knowflow:tasks:index"  # 索引任务流
    task_stream_dlq: str = "knowflow:tasks:dlq"  # 死信流
    task_consumer_group: str = "knowflow-indexer"
    task_consumer_name: str = "worker-1"
    task_max_retries: int = 3
    task_block_ms: int = 5000  # XREADGROUP 阻塞毫秒

    # ── Multi-Agent 编排 ──
    agent_timeout_seconds: int = 60  # 子 Agent 执行超时(秒)
    agent_max_subtasks: int = 5  # 主 Agent 最大委派子任务数

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_dsn(self) -> str:
        """异步 PG 连接串(asyncpg 驱动)."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def postgres_psycopg_dsn(self) -> str:
        """PG 连接串(psycopg 驱动, LangGraph AsyncPostgresSaver 用)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def allowed_types(self) -> list[str]:
        """上传允许的文件扩展名列表(小写)."""
        return [t.strip().lower() for t in self.upload_allowed_types.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS 允许来源列表."""
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

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
