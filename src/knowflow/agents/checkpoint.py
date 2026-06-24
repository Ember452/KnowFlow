"""CheckpointManager - 封装 LangGraph AsyncPostgresSaver.

提供 save/restore/lineage 四件套(对齐设计文档 3.4 模块三 CheckpointManager):
- save: 序列化 AgentState + 记录父子关系(原生 parent_checkpoint_id 自动维护)
- restore: 按 thread_id(+checkpoint_id)反序列化恢复状态(断点续跑)
- lineage: 沿原生 parent_checkpoint_id 向上回溯完整链路(replay 用)

thread_id 约定为 str(agent_run_id), 一个 run 一条线程; 线程内每次 save 自动
形成父子链. 决策背景见 docs/adr/0004-langgraph-checkpoint.md.
单测注入 InMemorySaver(langgraph.checkpoint.memory)即可, 不依赖真实 PG.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)


def _make_checkpoint(state: dict[str, Any], version: str) -> dict[str, Any]:
    """构造 LangGraph checkpoint dict(channel_values 承载 AgentState).

    字段对齐 langgraph.checkpoint.base.Checkpoint 结构: v/ts/id/channel_values/
    channel_versions/versions_seen/updated_channels. 状态整体存单一 channel
    "state", 经 new_versions/blob 机制落库(InMemorySaver/PostgresSaver 一致).
    """
    return {
        "v": 1,
        "ts": datetime.now(UTC).isoformat(),
        # uuid1 时间有序: InMemorySaver/PostgresSaver 均按 checkpoint_id 排序取最新
        "id": str(uuid.uuid1()),
        "channel_values": {"state": dict(state)},
        "channel_versions": {"state": version},
        "versions_seen": {},
        "updated_channels": None,
    }


def _config(thread_id: str, checkpoint_id: str | None = None) -> dict[str, Any]:
    """构造 RunnableConfig: thread_id 定位线程, checkpoint_id 定位版本."""
    configurable: dict[str, Any] = {"thread_id": thread_id, "checkpoint_ns": ""}
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


class CheckpointManager:
    """Checkpoint 门面. saver 可注入(单测 InMemorySaver), 否则懒加载 AsyncPostgresSaver."""

    def __init__(self, saver: Any | None = None, conn_string: str | None = None) -> None:
        """初始化.

        Args:
            saver: 注入的 saver(实现 aput/aget_tuple/setup). None 时懒加载
                AsyncPostgresSaver(生产, 需 conn_string 或 Settings 派生).
            conn_string: psycopg DSN; None 时用 Settings.postgres_psycopg_dsn.
        """
        self._saver: Any = saver
        self._conn_string = conn_string
        self._pool: Any = None

    async def initialize(self) -> None:
        """懒加载 saver 并建表(幂等). 生产路径首次 save/restore 前调用."""
        if self._saver is not None:
            return
        # 延迟导入: 避免模块加载时拉起 psycopg 连接
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        if self._conn_string is None:
            from knowflow.core.config import get_settings

            self._conn_string = get_settings().postgres_psycopg_dsn
        self._pool = AsyncConnectionPool(conninfo=self._conn_string, max_size=10, open=False)
        await self._pool.open()
        self._saver = AsyncPostgresSaver(self._pool)
        await self._saver.setup()
        logger.info("checkpoint.initialized")

    async def dispose(self) -> None:
        """释放连接池(应用关闭时调用)."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        self._saver = None

    async def get_saver(self) -> Any:
        """获取底层 saver(确保已初始化), 供 LangGraph compile(checkpointer=...) 使用."""
        await self.initialize()
        return self._saver

    async def save(
        self,
        state: dict[str, Any],
        thread_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """保存 checkpoint, 返回生成的 checkpoint_id.

        父子链: 自动取线程最新 checkpoint 作为父(连续 save 天然成链), 与 LangGraph
        状态机运行时语义一致; metadata 附加业务信息(run_id/session_id/节点名等).
        """
        await self.initialize()
        parent_id: str | None = None
        current_version: str | None = None
        latest = await self._saver.aget_tuple(_config(thread_id))
        if latest is not None:
            # 线程当前最新 checkpoint 即新 checkpoint 的父节点
            parent_id = latest.config.get("configurable", {}).get("checkpoint_id")
            current_version = latest.checkpoint.get("channel_versions", {}).get("state")
        version = self._saver.get_next_version(current_version, None)
        checkpoint = _make_checkpoint(state, version)
        returned = await self._saver.aput(
            _config(thread_id, parent_id),
            checkpoint,
            dict(metadata or {}),
            {"state": version},
        )
        checkpoint_id = str(returned["configurable"]["checkpoint_id"])
        logger.debug("checkpoint.saved", thread_id=thread_id, checkpoint_id=checkpoint_id)
        return checkpoint_id

    async def restore(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> dict[str, Any] | None:
        """恢复状态. checkpoint_id 缺省取线程最新 checkpoint.

        用于断点续跑: kill 后以同一 thread_id + 记录的 checkpoint_id 恢复.
        """
        await self.initialize()
        tup = await self._saver.aget_tuple(_config(thread_id, checkpoint_id))
        if tup is None:
            return None
        values = tup.checkpoint.get("channel_values", {})
        # 兼容单 channel "state" 存储与平铺 channel_values 两种形态
        return dict(values.get("state", values))

    async def lineage(
        self, thread_id: str, checkpoint_id: str | None = None
    ) -> list[dict[str, Any]]:
        """查询父子链路(从当前向上回溯到根), 顺序 [leaf, ..., root].

        每项含 checkpoint_id / parent_checkpoint_id / metadata / state / created_at.
        checkpoint_id 缺省从线程最新 checkpoint 开始回溯.
        """
        await self.initialize()
        chain: list[dict[str, Any]] = []
        if checkpoint_id is None:
            # 缺省从线程最新 checkpoint 开始回溯
            latest = await self._saver.aget_tuple(_config(thread_id))
            if latest is None:
                return []
            checkpoint_id = latest.config.get("configurable", {}).get("checkpoint_id")
        current_id = checkpoint_id
        seen: set[str] = set()
        while current_id is not None and current_id not in seen:
            seen.add(current_id)
            tup = await self._saver.aget_tuple(_config(thread_id, current_id))
            if tup is None:
                break
            # langgraph 1.x 的父子关系由 parent_config(内含上一 checkpoint_id)表达
            parent_config = tup.parent_config or {}
            parent_id = parent_config.get("configurable", {}).get("checkpoint_id")
            values = tup.checkpoint.get("channel_values", {})
            chain.append(
                {
                    "checkpoint_id": current_id,
                    "parent_checkpoint_id": parent_id,
                    "metadata": tup.metadata or {},
                    "state": dict(values.get("state", values)),
                    "created_at": tup.checkpoint.get("ts"),
                }
            )
            current_id = parent_id
        return chain
