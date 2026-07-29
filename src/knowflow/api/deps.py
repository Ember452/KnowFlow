"""FastAPI 依赖注入 - DB/Settings/Redis/MinIO/Retriever/Broker/租户上下文.

所有外部依赖通过 Depends 注入, 便于测试覆盖(app.dependency_overrides).
租户/用户上下文先做简单 header 透传, P11 补鉴权细节.
"""

import contextlib
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
    """构造并缓存 HybridRetriever 单例.

    接线: session_factory=get_session_factory(), hybrid_search 用共享单例
    (VectorStore/EmbeddingClient/BM25Store), reranker=get_reranker(), cache=RetrievalCache().
    """
    global _retriever
    if _retriever is not None:
        return _retriever

    from knowflow.retrieval.bm25_store import get_bm25_store
    from knowflow.retrieval.cache import RetrievalCache
    from knowflow.retrieval.embedding import get_embedding_client
    from knowflow.retrieval.hybrid_search import HybridSearch
    from knowflow.retrieval.reranker import get_reranker
    from knowflow.retrieval.retriever import HybridRetriever
    from knowflow.retrieval.vector_store import VectorStore

    hybrid = HybridSearch(
        vector_store=VectorStore(),
        bm25_store=get_bm25_store(),
        embedding_client=get_embedding_client(),
    )
    _retriever = HybridRetriever(
        session_factory=get_session_factory(),
        hybrid_search=hybrid,
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
    global \
        _skill_manager, \
        _tool_registry, \
        _orchestrator, \
        _context_manager, \
        _multi_agent, \
        _report_service
    _skill_manager = None
    _tool_registry = None
    _orchestrator = None
    _context_manager = None
    _multi_agent = None
    _report_service = None


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


# ── Multi-Agent 编排器(懒加载单例, 测试可覆盖) ──

_multi_agent: Any = None


def get_multi_agent_orchestrator() -> Any:
    """MultiAgentOrchestrator 单例: 主/子 Agent + checkpoint + session factory 装配.

    依赖未就绪(如 PG 不可用)时返回 None, 对话走直连链路, 不阻塞请求.
    测试可用 set_multi_agent_orchestrator 注入 fake.
    """
    global _multi_agent
    if _multi_agent is not None:
        return _multi_agent
    try:
        from knowflow.agents.checkpoint import CheckpointManager
        from knowflow.agents.orchestrator import MultiAgentOrchestrator
        from knowflow.core.llm import get_chat_llm
        from knowflow.db.base import get_session_factory

        _multi_agent = MultiAgentOrchestrator(
            llm=get_chat_llm(),
            session_factory=get_session_factory(),
            checkpoints=CheckpointManager(),
            # 子任务按需检索依赖 retriever; 不可用时编排器降级为共享上下文, 不阻塞
            retriever=get_retriever(),
            # 子 Agent 工具化: 复用工具编排器(SUBAGENT 角色可见 subagent_only 域);
            # 不可用(None)时子 Agent 回退纯 LLM 执行
            tool_orchestrator=get_tool_orchestrator(),
        )
        logger.info("deps.multi_agent_initialized")
    except Exception as exc:
        logger.warning("deps.multi_agent_unavailable", error=str(exc))
        _multi_agent = None
    return _multi_agent


def set_multi_agent_orchestrator(orchestrator: Any) -> None:
    """测试注入 multi_agent orchestrator(fake 或 None)."""
    global _multi_agent
    _multi_agent = orchestrator


async def dispose_multi_agent() -> None:
    """释放多 Agent 编排器(checkpoint 连接池), 应用关闭时调用."""
    global _multi_agent
    if _multi_agent is not None:
        with contextlib.suppress(Exception):
            dispose = getattr(_multi_agent, "dispose", None)
            if dispose is not None:
                await dispose()
        _multi_agent = None


MultiAgentDep = Annotated[Any, Depends(get_multi_agent_orchestrator)]


# ── Embedding 客户端(懒加载单例, 测试可覆盖) ──


def get_embedding_dep() -> Any:
    """Embedding 客户端依赖(长期记忆向量用). 测试可覆盖为 fake."""
    from knowflow.retrieval.embedding import get_embedding_client

    return get_embedding_client()


EmbeddingDep = Annotated[Any, Depends(get_embedding_dep)]


# ── 报告流水线(懒加载单例, 测试可覆盖) ──

_report_service: Any = None


class _SessionRecaller:
    """请求级长期记忆召回器: 每次调用独立 session(报告调研/记忆工具懒加载用)."""

    async def recall(self, query: str, user_id: str, top_k: int | None = None) -> list[Any]:
        from knowflow.db.base import get_session_factory
        from knowflow.memory.long_term import LongTermMemoryManager
        from knowflow.retrieval.embedding import get_embedding_client

        factory = get_session_factory()
        async with factory() as session:
            manager = LongTermMemoryManager(session, embedding_client=get_embedding_client())
            return await manager.recall(query, user_id, top_k=top_k)


def get_report_service() -> Any:
    """ReportService 单例: 报告流水线 + 发布器装配.

    依赖未就绪(如 LLM/检索器不可用)时返回 None, 报告端点返回 503(不阻塞对话链路).
    测试可用 set_report_service 注入 fake.
    """
    global _report_service
    if _report_service is not None:
        return _report_service
    try:
        from knowflow.agents.report.pipeline import ReportPipeline
        from knowflow.agents.report.publisher import McpPublishAdapter, ReportPublisher
        from knowflow.core.llm import get_chat_llm
        from knowflow.db.minio import get_minio
        from knowflow.sandbox.workspace import WorkspaceManager
        from knowflow.services.report_service import ReportService
        from knowflow.tools.builtin.search_tool import SearchTool

        _report_service = ReportService(
            pipeline=ReportPipeline(
                llm=get_chat_llm(),
                retriever=get_retriever(),
                recaller=_SessionRecaller(),
                search=SearchTool(),
                workspace_manager=WorkspaceManager(get_minio()),
            ),
            # 发布器: 经 MCP 注册表解析 mcp_feishu_* 工具; 未配置飞书时发布返回可读降级提示
            publisher=ReportPublisher(adapter=McpPublishAdapter(get_tool_registry())),
        )
        logger.info("deps.report_service_initialized")
    except Exception as exc:
        logger.warning("deps.report_service_unavailable", error=str(exc))
        _report_service = None
    return _report_service


def set_report_service(service: Any) -> None:
    """测试注入 report_service(fake 或 None)."""
    global _report_service
    _report_service = service


ReportServiceDep = Annotated[Any, Depends(get_report_service)]
