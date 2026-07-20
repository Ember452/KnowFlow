"""索引 Worker 主进程 - 消费 Redis Stream 索引任务, 调 RetrievalPipeline.

启动: `uv run python -m worker.main` 或 `make worker`.
流程: init 依赖(PG/Redis/Milvus/MinIO) → ensure_group → 消费循环 → 优雅退出.
重试策略: 失败时若 attempts < max_retries 重新入队(attempts+1), 否则入死信队列.
"""

import asyncio
import contextlib
import signal

from knowflow.core.config import get_settings
from knowflow.core.logging import get_logger, setup_logging
from knowflow.tasks.broker import TaskBroker
from knowflow.tasks.index_task import build_index_deps, handle_index_task
from worker.settings import WorkerSettings

logger = get_logger("worker")

_RETRY_BASE_DELAY_S = 1.0  # Redis 故障重试初始退避(秒)
_RETRY_MAX_DELAY_S = 30.0  # 退避上限(秒)


async def _init_deps() -> None:
    """初始化全部外部依赖(与 API 共用单例)."""
    from knowflow.db.base import dispose_engine, get_session_factory, init_engine
    from knowflow.db.milvus import dispose_milvus, init_milvus
    from knowflow.db.minio import dispose_minio, init_minio
    from knowflow.db.redis import dispose_redis, init_redis
    from knowflow.retrieval.bm25_store import init_bm25_store

    await init_engine()
    # BM25 启动时从 chunks 表全量加载(与 API 进程各自持有同源索引, 增量不跨进程同步)
    await init_bm25_store(get_session_factory())
    await init_redis()
    init_minio()
    # 索引任务写入向量, 必须在消费前建立 Milvus 连接(VectorStore 构造时取单例, 非懒加载)
    init_milvus()
    # 注册关闭(逆序)
    _SHUTDOWN.append(dispose_minio)
    _SHUTDOWN.append(dispose_redis)
    _SHUTDOWN.append(dispose_milvus)
    _SHUTDOWN.append(dispose_engine)


_SHUTDOWN: list = []


async def _dispose() -> None:
    for fn in reversed(_SHUTDOWN):
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            logger.warning("worker.dispose_failed", error=str(exc))


async def run() -> None:
    """Worker 主循环."""
    setup_logging()
    settings = get_settings()
    ws = WorkerSettings.from_settings()
    logger.info("worker.starting", env=settings.env, stream=ws.stream, group=ws.group)

    await _init_deps()
    from knowflow.db.redis import get_redis

    broker = TaskBroker(get_redis())
    await broker.ensure_group(ws.stream, ws.group)

    stop_event = asyncio.Event()

    def _on_signal() -> None:
        logger.info("worker.stop_signal")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _on_signal)

    logger.info("worker.consuming", consumer=ws.consumer, block_ms=ws.block_ms)
    try:
        await _consume_loop(broker, ws, stop_event)
    finally:
        await _dispose()
        logger.info("worker.stopped")


async def _consume_loop(broker: TaskBroker, ws: WorkerSettings, stop_event: asyncio.Event) -> None:
    """消费循环: 处理消息; Redis 瞬时故障(超时/断连)时指数退避重试, 保持进程存活.

    虚拟机 Redis 偶发抖动/超时会中断阻塞读, 直接抛出会让 worker 进程崩溃退出;
    此处捕获后短暂退避重试, 恢复后自动继续消费, 无需人工重启.
    """
    retry_delay = _RETRY_BASE_DELAY_S
    while not stop_event.is_set():
        try:
            messages = await broker.consume(
                ws.stream, ws.group, ws.consumer, count=ws.batch_size, block_ms=ws.block_ms
            )
            retry_delay = _RETRY_BASE_DELAY_S
        except (TimeoutError, ConnectionError, OSError) as exc:
            logger.error(
                "worker.redis_unavailable",
                error=str(exc),
                retry_in_s=round(retry_delay, 1),
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, _RETRY_MAX_DELAY_S)
            continue
        for msg in messages:
            await _process(broker, ws, msg)


async def _process(broker: TaskBroker, ws: WorkerSettings, msg: object) -> None:
    """处理单条消息: 执行任务 → 成功 ack; 失败重试或入 DLQ."""
    payload = msg.payload  # type: ignore[attr-defined]
    msg_id = msg.id  # type: ignore[attr-defined]
    attempts = int(payload.get("attempts", 0))

    try:
        result = await handle_index_task(payload, build_index_deps)
    except Exception as exc:
        # 非预期异常, 视为可重试
        logger.error("worker.task_exception", msg_id=msg_id, error=str(exc))
        result = {"ok": False, "retryable": True, "doc_id": payload.get("doc_id")}

    if result["ok"]:
        try:
            await broker.ack(ws.stream, ws.group, msg_id)
        except Exception as exc:
            # ack 失败(Redis 抖动): 记录日志不中断消费循环; 消息留 PEL 供审计/补偿
            logger.error("worker.ack_failed", msg_id=msg_id, error=str(exc))
        return

    if result["retryable"] and attempts + 1 < ws.max_retries:
        payload["attempts"] = attempts + 1
        try:
            await broker.enqueue(ws.stream, payload)
            await broker.ack(ws.stream, ws.group, msg_id)
            logger.warning(
                "worker.requeued", msg_id=msg_id, attempts=attempts + 1, doc_id=result["doc_id"]
            )
        except Exception as exc:
            # 重试入队/ack 失败: 记录日志不中断消费循环; 消息留在 PEL 供人工审计
            logger.error("worker.requeue_failed", msg_id=msg_id, error=str(exc))
    else:
        try:
            await broker.send_to_dlq(ws.dlq_stream, msg_id, payload, reason="max retries exceeded")
            await broker.ack(ws.stream, ws.group, msg_id)
        except Exception as exc:
            logger.error("worker.dlq_failed", msg_id=msg_id, error=str(exc))


def main() -> None:
    """进程入口."""
    asyncio.run(run())


if __name__ == "__main__":
    main()
