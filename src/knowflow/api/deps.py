"""FastAPI 依赖注入 - DB/Settings/Redis/MinIO/Retriever/Broker/租户上下文.

所有外部依赖通过 Depends 注入, 便于测试覆盖(app.dependency_overrides).
租户/用户上下文先做简单 header 透传, P11 补鉴权细节.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger
from knowflow.db.base import get_session_factory

logger = get_logger(__name__)


async def get_db() -> AsyncIterator[AsyncSession]:
    """请求级 AsyncSession 依赖. 事务边界由 service 层管理.

    重导出自 knowflow.db.base, 集中依赖入口便于统一覆盖.
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session


DbDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_redis_dep() -> Any:
    """Redis 客户端依赖(单例). 未初始化时抛 RuntimeError, 由 readyz 反映."""
    from knowflow.db.redis import get_redis

    return get_redis()


RedisDep = Annotated[Any, Depends(get_redis_dep)]


def get_minio_dep() -> Any:
    """MinIO 客户端依赖(单例)."""
    from knowflow.db.minio import get_minio

    return get_minio()


MinioDep = Annotated[Any, Depends(get_minio_dep)]


def get_broker_dep() -> Any:
    """TaskBroker 依赖. 基于 Redis 单例构造, 测试可覆盖."""
    from knowflow.tasks.broker import TaskBroker

    return TaskBroker(get_redis_dep())


BrokerDep = Annotated[Any, Depends(get_broker_dep)]


def get_llm_dep() -> Any:
    """ChatOpenAI 单例依赖(懒加载). 测试可覆盖为 fake."""
    from knowflow.core.llm import get_chat_llm

    return get_chat_llm()


LlmDep = Annotated[Any, Depends(get_llm_dep)]


def get_current_user(
    x_user_id: Annotated[str | None, Header()] = None,
) -> str:
    """从 X-User-Id header 取用户标识. 缺省返回 'anonymous'.

    M3 仅做透传, P11 接 JWT/SSO 鉴权.
    """
    return x_user_id or "anonymous"


UserDep = Annotated[str, Depends(get_current_user)]

# ── 检索器单例(懒加载, 测试可 set_retriever 覆盖) ──

_retriever: Any = None


def get_retriever() -> Any:
    """构造并缓存 GraphRAGRetriever 单例.

    接线: session_factory=get_session_factory(), hybrid_search 用共享单例
    (VectorStore/EmbeddingClient/BM25Store), expander_factory 按调用构造,
    reranker=get_reranker(), cache=RetrievalCache().
    """
    global _retriever
    if _retriever is not None:
        return _retriever

    from knowflow.retrieval.bm25_store import get_bm25_store
    from knowflow.retrieval.cache import RetrievalCache
    from knowflow.retrieval.embedding import get_embedding_client
    from knowflow.retrieval.expander import Expander
    from knowflow.retrieval.hybrid_search import HybridSearch
    from knowflow.retrieval.reranker import get_reranker
    from knowflow.retrieval.retriever import GraphRAGRetriever
    from knowflow.retrieval.vector_store import VectorStore

    hybrid = HybridSearch(
        vector_store=VectorStore(),
        bm25_store=get_bm25_store(),
        embedding_client=get_embedding_client(),
    )
    _retriever = GraphRAGRetriever(
        session_factory=get_session_factory(),
        hybrid_search=hybrid,
        expander_factory=lambda session: Expander(session),
        reranker=get_reranker(),
        cache=RetrievalCache(),
    )
    logger.info("deps.retriever_initialized")
    return _retriever


def set_retriever(retriever: Any) -> None:
    """测试注入 retriever."""
    global _retriever
    _retriever = retriever


def dispose_retriever() -> None:
    global _retriever
    _retriever = None


RetrieverDep = Annotated[Any, Depends(get_retriever)]


# ── Skill 管理器与工具注册表(懒加载单例, 测试可覆盖) ──

_skill_manager: Any = None
_tool_registry: Any = None


def get_skill_manager() -> Any:
    """SkillManager 单例: 加载 skills/ 目录下 SKILL.md 并维护运行时启停状态."""
    global _skill_manager
    if _skill_manager is not None:
        return _skill_manager
    from knowflow.tools.skill_manager import SkillManager

    _skill_manager = SkillManager()
    logger.info("deps.skill_manager_initialized")
    return _skill_manager


def set_skill_manager(manager: Any) -> None:
    """测试注入 SkillManager."""
    global _skill_manager
    _skill_manager = manager


def get_tool_registry() -> Any:
    """ToolRegistry 单例: 注册全部内置工具(检索/文件/搜索/计算器)."""
    global _tool_registry
    if _tool_registry is not None:
        return _tool_registry
    from knowflow.tools.builtin import build_default_registry

    _tool_registry = build_default_registry()
    logger.info("deps.tool_registry_initialized")
    return _tool_registry


def set_tool_registry(registry: Any) -> None:
    """测试注入 ToolRegistry."""
    global _tool_registry
    _tool_registry = registry


def dispose_tools() -> None:
    """释放工具治理单例."""
    global _skill_manager, _tool_registry
    _skill_manager = None
    _tool_registry = None


SkillManagerDep = Annotated[Any, Depends(get_skill_manager)]
ToolRegistryDep = Annotated[Any, Depends(get_tool_registry)]
