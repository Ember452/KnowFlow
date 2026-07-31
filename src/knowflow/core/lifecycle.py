"""FastAPI 生命周期管理 - 启动建连接池, 关闭优雅释放.

开发环境允许单个依赖初始化失败(不阻塞启动), 健康检查端点会反映真实状态;
生产环境严格失败即退出.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger, setup_logging
from knowflow.core.telemetry import setup_telemetry

logger = get_logger("lifecycle")


async def _safe_init(name: str, init_fn: Callable[[], Awaitable[Any] | Any]) -> bool:
    """执行单个依赖初始化, 失败时记录警告并返回 False(不抛出)."""
    try:
        result = init_fn()
        if asyncio.iscoroutine(result):
            await result
        logger.info("lifecycle.dependency_ready", dependency=name)
        return True
    except Exception as exc:
        settings = get_settings()
        if settings.is_prod:
            logger.error("lifecycle.dependency_failed_fatal", dependency=name, error=str(exc))
            raise
        logger.warning(
            "lifecycle.dependency_failed_skip",
            dependency=name,
            error=str(exc),
        )
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期: 初始化日志 -> telemetry -> 四件套依赖 -> yield -> 释放."""
    setup_logging()
    setup_telemetry()
    settings = get_settings()
    logger.info("lifecycle.starting", app=settings.app_name, env=settings.env)

    # 延迟导入避免循环依赖
    from knowflow.db.base import dispose_engine, init_engine
    from knowflow.db.milvus import dispose_milvus, init_milvus
    from knowflow.db.minio import dispose_minio, init_minio
    from knowflow.db.redis import dispose_redis, init_redis

    # ── startup: 依次初始化依赖 ──
    await _safe_init("postgres", init_engine)
    await _safe_init("bm25", _load_bm25)
    await _safe_init("redis", init_redis)
    await _safe_init("milvus", init_milvus)
    await _safe_init("minio", init_minio)
    await _safe_init("mcp_tools", _init_mcp_tools)

    yield

    # ── shutdown: 逆序释放 ──
    await _safe_init("milvus", dispose_milvus)
    await _safe_init("minio", dispose_minio)
    await _safe_init("redis", dispose_redis)
    await _safe_init("postgres", dispose_engine)
    _dispose_ai_singletons()
    await _dispose_multi_agent()
    logger.info("lifecycle.stopped")


async def _load_bm25() -> None:
    """从 chunks 表全量加载 BM25 内存索引(重启后恢复, 失败不阻塞启动)."""
    from knowflow.db.base import get_session_factory
    from knowflow.retrieval.bm25_store import init_bm25_store

    await init_bm25_store(get_session_factory())


async def _init_mcp_tools() -> None:
    """注册配置声明的 MCP Server 工具(单个不可用降级, 不阻塞其他注册)."""
    from knowflow.api.deps import get_tool_registry
    from knowflow.core.constants import ExecutionDomain
    from knowflow.tools.mcp.register import register_mcp_server

    settings = get_settings()
    registry = get_tool_registry()
    for cfg in settings.mcp_servers:
        server_id = str(cfg.get("id", "")).strip()
        command = str(cfg.get("command", "")).strip()
        if not server_id or not command:
            logger.warning("mcp.config_skip", cfg=cfg)
            continue
        try:
            domain = ExecutionDomain(str(cfg.get("domain", "skill_only")))
        except ValueError:
            domain = ExecutionDomain.SKILL_ONLY
        args = [str(a) for a in cfg.get("args", [])]
        allow_tools_raw = cfg.get("allow_tools")
        allow_tools = [str(t) for t in allow_tools_raw] if allow_tools_raw else None
        env_raw = cfg.get("env")
        env = {str(k): str(v) for k, v in env_raw.items()} if env_raw else None
        await register_mcp_server(
            registry, server_id, command, args, domain=domain, env=env, allow_tools=allow_tools
        )


def _dispose_ai_singletons() -> None:
    """释放 LLM/Embedding/Reranker 懒加载单例(未加载时无操作, 失败忽略)."""
    with contextlib.suppress(Exception):
        from knowflow.core.llm import dispose_chat_llm

        dispose_chat_llm()
    with contextlib.suppress(Exception):
        from knowflow.retrieval.embedding import dispose_embedding_client

        dispose_embedding_client()
    with contextlib.suppress(Exception):
        from knowflow.retrieval.reranker import dispose_reranker

        dispose_reranker()


async def _dispose_multi_agent() -> None:
    """释放多 Agent 编排器(checkpoint 连接池), 未加载时无操作."""
    from knowflow.api.deps import dispose_multi_agent

    await dispose_multi_agent()
