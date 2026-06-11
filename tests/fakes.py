"""测试用 fake 组件 - MinIO / Broker / Redis / Retriever.

供 document_service / endpoint / broker / index_task 单测注入, 避免真实依赖.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeMinio:
    """记录 put_object / remove_object / fget_object 调用."""

    put_calls: list[tuple[str, str, bytes]] = field(default_factory=list)
    remove_calls: list[str] = field(default_factory=list)
    objects: dict[str, bytes] = field(default_factory=dict)

    def put_object(
        self, bucket: str, name: str, data: Any, length: int, content_type: str = ""
    ) -> Any:
        content = data.read() if hasattr(data, "read") else bytes(data)
        self.put_calls.append((bucket, name, content))
        self.objects[name] = content
        return None

    def remove_object(self, bucket: str, name: str) -> None:
        self.remove_calls.append(name)
        self.objects.pop(name, None)

    def fget_object(self, bucket: str, name: str, file_path: str) -> Any:
        with open(file_path, "wb") as f:
            f.write(self.objects.get(name, b""))
        return None

    def bucket_exists(self, bucket: str) -> bool:
        return True


@dataclass
class FakeBroker:
    """记录 enqueue 调用, 不真正入队."""

    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    acked: list[tuple[str, str]] = field(default_factory=list)
    dlq: list[tuple[str, dict[str, Any], str]] = field(default_factory=list)

    async def ensure_group(self, stream: str, group: str) -> None:
        return None

    async def enqueue(self, stream: str, payload: dict[str, Any], **_: Any) -> str:
        self.enqueued.append((stream, payload))
        return f"msg-{len(self.enqueued)}"

    async def consume(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def ack(self, stream: str, group: str, msg_id: str) -> int:
        self.acked.append((stream, msg_id))
        return 1

    async def send_to_dlq(
        self, dlq_stream: str, msg_id: str, payload: dict[str, Any], reason: str
    ) -> str:
        self.dlq.append((msg_id, payload, reason))
        return f"dlq-{msg_id}"


class FakeRedisStream:
    """内存 Redis Stream 实现, 支持 xadd/xreadgroup/xack/xgroup_create/xlen.

    用于 TaskBroker 单测. decode_responses=True 语义: 字段值为 str.
    """

    def __init__(self) -> None:
        self._streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        # (stream, group) -> PEL(已投递未 ack 的 msg_id)
        self._groups: dict[tuple[str, str], set[str]] = {}
        # (stream, group) -> 已投递过的 msg_id(`>` 不重复投递)
        self._delivered: dict[tuple[str, str], set[str]] = {}
        self._ids: dict[str, int] = {}  # stream -> counter

    def _next_id(self, stream: str) -> str:
        self._ids[stream] = self._ids.get(stream, 0) + 1
        return f"{self._ids[stream]}-0"

    async def xadd(
        self, stream: str, data: dict[str, str], maxlen: int = 0, approximate: bool = False
    ) -> str:
        msg_id = self._next_id(stream)
        self._streams.setdefault(stream, []).append((msg_id, dict(data)))
        return msg_id

    async def xgroup_create(
        self, stream: str, group: str, id: str = "0", mkstream: bool = False
    ) -> Any:
        if mkstream and stream not in self._streams:
            self._streams[stream] = []
        key = (stream, group)
        if key in self._groups:
            raise Exception("BUSYGROUP Consumer Group name already exists")
        self._groups[key] = set()
        self._delivered[key] = set()
        return True

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int = 1,
        block: int = 0,
    ) -> list[Any]:
        result: list[Any] = []
        for stream, _start in streams.items():
            key = (stream, groupname)
            if key not in self._groups:
                continue
            entries = self._streams.get(stream, [])
            delivered = self._delivered.setdefault(key, set())
            picked: list[Any] = []
            for msg_id, data in entries:
                if msg_id in delivered:
                    continue  # `>` 不重复投递已投递过的消息
                delivered.add(msg_id)
                self._groups[key].add(msg_id)  # 进入 PEL
                picked.append((msg_id, data))
                if len(picked) >= count:
                    break
            if picked:
                result.append((stream, picked))
        return result

    async def xack(self, stream: str, group: str, *msg_ids: str) -> int:
        key = (stream, group)
        n = 0
        for mid in msg_ids:
            if key in self._groups and mid in self._groups[key]:
                self._groups[key].discard(mid)
                n += 1
        return n

    async def xlen(self, stream: str) -> int:
        return len(self._streams.get(stream, []))


@dataclass(frozen=True)
class FakeChunkWithScore:
    chunk_id: int
    content: str
    score: float
    source: str


@dataclass(frozen=True)
class FakeRetrievalResult:
    chunks: list[FakeChunkWithScore] = field(default_factory=list)
    query: str = ""
    latency_ms: float = 0.0
    cache_hit: bool = False


class FakeRetriever:
    """固定返回的检索器, 用于 knowledge endpoint 测试."""

    def __init__(self, chunks: Sequence[FakeChunkWithScore] | None = None) -> None:
        self._chunks = list(chunks or [])
        self.calls: list[dict[str, Any]] = []

    async def retrieve(self, query: str, **kwargs: Any) -> FakeRetrievalResult:
        self.calls.append({"query": query, **kwargs})
        return FakeRetrievalResult(
            chunks=self._chunks,
            query=query,
            latency_ms=1.0,
            cache_hit=False,
        )
