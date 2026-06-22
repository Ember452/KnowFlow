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
    global _skill_manager, _tool_registry, _orchestrator, _context_manager
    _skill_manager = None
    _tool_registry = None
    _orchestrator = None
    _context_manager = None


SkillManagerDep = Annotated[Any, Depends(get_skill_manager)]
ToolRegistryDep = Annotated[Any, Depends(get_tool_registry)]


# ── 工具编排器(懒加载单例, 测试可覆盖) ──

_orchestrator: Any = None


def get_tool_orchestrator() -> Any:
    """ToolOrchestrator 单例: registry + skill_manager + llm 装配.

    依赖未就绪(如 MinIO 未初始化)时返回 None, 对话回退直连检索链路, 不阻塞请求.
    测试可用 set_tool_orchestrator 注入 fake.
    """
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    from knowflow.core.llm import get_chat_llm
    from knowflow.services.tool_orchestrator import ToolOrchestrator

    try:
        _orchestrator = ToolOrchestrator(
            registry=get_tool_registry(),
            skill_manager=get_skill_manager(),
            llm=get_chat_llm(),
        )
        logger.info("deps.tool_orchestrator_initialized")
    except Exception as exc:
        logger.warning("deps.tool_orchestrator_unavailable", error=str(exc))
        _orchestrator = None
    return _orchestrator


def set_tool_orchestrator(orchestrator: Any) -> None:
    """测试注入 orchestrator(fake 或 None)."""
    global _orchestrator
    _orchestrator = orchestrator


OrchestratorDep = Annotated[Any, Depends(get_tool_orchestrator)]


# ── 上下文管理器(懒加载单例, 测试可覆盖) ──

_context_manager: Any = None


def get_context_manager() -> Any:
    """ContextManager 单例: 窗口/摘要/卸载/预算编排.

    依赖 LLM/MinIO 未就绪时返回 None(直连链路用内置组装), 不阻塞请求.
    测试可用 set_context_manager 注入 fake.
    """
    global _context_manager
    if _context_manager is not None:
        return _context_manager
    try:
        from knowflow.context.spiller import Spiller
        from knowflow.context.strategy import ContextManager, ContextStrategy
        from knowflow.context.summarizer import Summarizer
        from knowflow.core.llm import get_chat_llm
        from knowflow.db.minio import get_minio
        from knowflow.sandbox.workspace import WorkspaceManager

        strategy = ContextStrategy(
            summarizer=Summarizer(get_chat_llm()),
            spiller=Spiller(WorkspaceManager(get_minio())),
        )
        _context_manager = ContextManager(strategy=strategy)
        logger.info("deps.context_manager_initialized")
    except Exception as exc:
        logger.warning("deps.context_manager_unavailable", error=str(exc))
        _context_manager = None
    return _context_manager


def set_context_manager(manager: Any) -> None:
    """测试注入 context_manager(fake 或 None)."""
    global _context_manager
    _context_manager = manager


ContextManagerDep = Annotated[Any, Depends(get_context_manager)]


# ── Embedding 客户端(懒加载单例, 测试可覆盖) ──


def get_embedding_dep() -> Any:
    """Embedding 客户端依赖(长期记忆向量用). 测试可覆盖为 fake."""
    from knowflow.retrieval.embedding import get_embedding_client

    return get_embedding_client()


EmbeddingDep = Annotated[Any, Depends(get_embedding_dep)]
