"""任务队列封装 - 基于 Redis Stream (XADD/XREADGROUP/XACK).

设计:
- 每个任务为 Stream 上一条消息, payload JSON 编码进单个字段 "payload".
- 消费组保证每条消息被一个 consumer 消费(XREADGROUP >).
- 失败重试: 由 worker 决策, 重新 XADD 一条 attempts+1 的消息; 超过 max_retries 入 DLQ.
- ack 后消息从 PEL 删除.

不引入 Celery: 异步索引是单一任务类型, Redis Stream 原生足够, 减少依赖.
"""

import json
from dataclasses import dataclass
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_PAYLOAD_FIELD = "payload"
_DEFAULT_MAX_LEN = 10000  # Stream 近似最大长度(XADD MAXLEN ~)


@dataclass(frozen=True)
class StreamMessage:
    """从 Stream 消费出的一条消息."""

    id: str
    payload: dict[str, Any]


class TaskBroker:
    """Redis Stream 任务队列."""

    def __init__(self, redis: Any) -> None:
        """初始化.

        Args:
            redis: redis.asyncio.Redis 客户端(或测试 fake, 需实现 xadd/xreadgroup/
                xack/xgroup/xlen).
        """
        self._redis = redis

    async def ensure_group(self, stream: str, group: str) -> None:
        """确保消费组存在(不存在则创建, 已存在忽略)."""
        try:
            await self._redis.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info("broker.group_created", stream=stream, group=group)
        except Exception as exc:
            # BUSYGROUP: 组已存在
            if "BUSYGROUP" in str(exc):
                return
            raise

    async def enqueue(
        self,
        stream: str,
        payload: dict[str, Any],
        *,
        max_len: int = _DEFAULT_MAX_LEN,
    ) -> str:
        """投递任务. 返回消息 id."""
        data = {_PAYLOAD_FIELD: json.dumps(payload, ensure_ascii=False, default=str)}
        msg_id: str = await self._redis.xadd(stream, data, maxlen=max_len, approximate=True)
        logger.info("broker.enqueued", stream=stream, msg_id=msg_id, task=payload.get("task"))
        return msg_id

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        *,
        count: int = 1,
        block_ms: int = 5000,
    ) -> list[StreamMessage]:
        """消费一批消息(XREADGROUP >). 阻塞 block_ms 毫秒. 无消息返回空列表."""
        raw = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )
        if not raw:
            return []
        # raw: [(stream, [(msg_id, {field: value}), ...])]
        messages: list[StreamMessage] = []
        for _stream, entries in raw:
            for msg_id, fields in entries:
                payload_field = fields.get(_PAYLOAD_FIELD, "{}")
                if isinstance(payload_field, bytes):
                    payload_field = payload_field.decode("utf-8")
                try:
                    payload = json.loads(payload_field)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("broker.invalid_payload", msg_id=msg_id, raw=payload_field)
                    payload = {}
                messages.append(StreamMessage(id=msg_id, payload=payload))
        return messages

    async def ack(self, stream: str, group: str, msg_id: str) -> int:
        """确认消息(XACK). 返回 ack 条数."""
        n: int = await self._redis.xack(stream, group, msg_id)
        return n

    async def send_to_dlq(
        self,
        dlq_stream: str,
        msg_id: str,
        payload: dict[str, Any],
        reason: str,
    ) -> str:
        """转入死信队列."""
        dlq_payload = {**payload, "_failed_msg_id": msg_id, "_reason": reason}
        data = {_PAYLOAD_FIELD: json.dumps(dlq_payload, ensure_ascii=False, default=str)}
        dlq_id: str = await self._redis.xadd(
            dlq_stream, data, maxlen=_DEFAULT_MAX_LEN, approximate=True
        )
        logger.error("broker.sent_to_dlq", dlq_id=dlq_id, failed_msg_id=msg_id, reason=reason)
        return dlq_id
