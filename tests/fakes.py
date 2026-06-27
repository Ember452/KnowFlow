"""测试用 fake 组件 - MinIO / Broker / Redis / Retriever.

供 document_service / endpoint / broker / index_task 单测注入, 避免真实依赖.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeMinioObject:
    """FakeMinio 对象元信息(对齐 minio.list_objects/stat_object 返回)."""

    object_name: str
    size: int
    content_type: str = "application/octet-stream"


class _FakeObjectStream:
    """FakeMinio get_object 返回的可读流(对齐 urllib3 响应接口)."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._read = False

    def read(self) -> bytes:
        if self._read:
            return b""
        self._read = True
        return self._data

    def stream(self, *_a: Any, **_kw: Any) -> Any:
        yield self._data

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass


@dataclass
class FakeMinio:
    """记录 put_object / remove_object / fget_object 调用.

    支持沙盒后端所需: put/get/list/remove/stat. objects 字段为对象全量内容,
    list_objects 按 prefix 过滤返回 FakeMinioObject.
    """

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

    def get_object(self, bucket: str, name: str) -> _FakeObjectStream:
        if name not in self.objects:
            raise KeyError(f"object not found: {name}")
        return _FakeObjectStream(self.objects[name])

    def list_objects(
        self, bucket: str, prefix: str | None = None, recursive: bool = False
    ) -> list[FakeMinioObject]:
        names = sorted(self.objects)
        if prefix:
            names = [n for n in names if n.startswith(prefix)]
        return [FakeMinioObject(object_name=n, size=len(self.objects[n])) for n in names]

    def stat_object(self, bucket: str, name: str) -> FakeMinioObject:
        if name not in self.objects:
            raise KeyError(f"object not found: {name}")
        return FakeMinioObject(object_name=name, size=len(self.objects[name]))

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


@dataclass
class FakeChatLLM:
    """fake LLM, 记录 ainvoke/astream 调用, 用于对话服务/端点单测.

    astream 按 token_chunks 逐段产出; 注入 raise_on_stream 可测异常路径.
    """

    answer: str = "这是来自 KnowFlow 的回复。"
    token_chunks: tuple[str, ...] = ("这是", "来自", "KnowFlow", "的回复。")
    invoke_calls: int = 0
    stream_calls: int = 0
    last_messages: list[Any] = field(default_factory=list)
    raise_on_stream: bool = False

    async def ainvoke(self, messages: list[Any]) -> str:
        self.invoke_calls += 1
        self.last_messages = list(messages)
        return self.answer

    async def astream(self, messages: list[Any]) -> AsyncIterator[str]:
        self.stream_calls += 1
        self.last_messages = list(messages)
        if self.raise_on_stream:
            raise RuntimeError("fake llm stream failed")
        for token in self.token_chunks:
            yield token


@dataclass
class _ScriptedResponse:
    """FakeToolCallingLLM 单次响应: 含 content 与可选 tool_calls(dict, 对齐 langchain)."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class FakeToolCallingLLM:
    """支持 bind_tools 与 tool_calls 的 fake LLM, 用于 ToolOrchestrator 单测.

    按脚本顺序返回响应: 先返回带 tool_calls 的响应, 工具结果回填后返回最终 content.
    bind_tools 记录注入的工具定义, 便于断言可见工具集. tool_calls 为 dict 列表
    (含 name/args/id), 对齐 langchain AIMessage.tool_calls 格式.
    """

    def __init__(self, script: list[_ScriptedResponse]) -> None:
        self._script = list(script)
        self._idx = 0
        self.bound_tools: list[Any] = []
        self.invoke_calls = 0
        self.last_messages: list[Any] = []

    def bind_tools(self, tools: list[Any]) -> "FakeToolCallingLLM":
        self.bound_tools = list(tools)
        return self

    async def ainvoke(self, messages: list[Any]) -> _ScriptedResponse:
        self.invoke_calls += 1
        self.last_messages = list(messages)
        if self._idx >= len(self._script):
            return _ScriptedResponse(content="(脚本已耗尽)")
        resp = self._script[self._idx]
        self._idx += 1
        return resp


@dataclass
class FakeToolOrchestrator:
    """fake 工具编排器: 固定返回编排结果, 记录 run 调用参数.

    用于 ChatService 工具链路单测, 避免依赖真实 LLM/注册表.
    """

    answer: str = "这是工具编排的回复。"
    tool_calls: list[Any] = field(default_factory=list)
    no_tools: bool = False
    run_calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        query: str,
        session_id: str | None = None,
        agent_role: Any = None,
        history: list[dict[str, str]] | None = None,
        context: str | None = None,
        active_skills: list[Any] | None = None,
    ) -> Any:
        from knowflow.services.tool_orchestrator import OrchestratorResult

        self.run_calls.append(
            {
                "query": query,
                "session_id": session_id,
                "history": history,
                "context": context,
            }
        )
        return OrchestratorResult(
            answer=self.answer, tool_calls=list(self.tool_calls), no_tools=self.no_tools
        )


@dataclass
class FakeMultiAgentOrchestrator:
    """fake 多 Agent 编排器: 固定返回编排结果, 记录 run 调用参数.

    用于 ChatService 多 Agent 链路单测. intent="simple" 时 answer 为空
    (调用方回退直连链路), 与真实编排器信号约定一致.
    """

    answer: str = "这是多 Agent 编排的回复。"
    intent: str = "complex"
    delegated: bool = True
    subtasks: list[Any] = field(default_factory=list)
    raise_failure: bool = False
    run_calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        query: str,
        session_id: int | None = None,
        context: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> Any:
        from knowflow.agents.orchestrator import MultiAgentResult

        self.run_calls.append(
            {"query": query, "session_id": session_id, "context": context, "history": history}
        )
        if self.raise_failure:
            raise RuntimeError("checkpoint PG 不可用")
        return MultiAgentResult(
            run_id=1,
            delegated=self.delegated,
            answer=self.answer if self.intent == "complex" else "",
            intent=self.intent,
            subtasks=list(self.subtasks),
            checkpoint_id="ckpt-1",
            latency_ms=10.0,
        )


class FakeRedisList:
    """内存 Redis List 桩(短期记忆用): rpush/lrange/expire/delete/llen.

    lrange 支持负数索引(对齐 Redis 语义), expire 为无操作(TTL 语义由真实 Redis 提供).
    """

    def __init__(self) -> None:
        self._store: dict[str, list[str]] = {}
        self.expired: list[tuple[str, int]] = []

    async def rpush(self, key: str, value: str) -> int:
        self._store.setdefault(key, []).append(value)
        return len(self._store[key])

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        items = self._store.get(key, [])
        n = len(items)
        start = max(0, n + start) if start < 0 else start
        end = (n + end) if end < 0 else min(n - 1, end)
        return items[start : end + 1]

    async def expire(self, key: str, ttl: int) -> bool:
        self.expired.append((key, ttl))
        return key in self._store

    async def delete(self, key: str) -> int:
        return int(self._store.pop(key, None) is not None)

    async def llen(self, key: str) -> int:
        return len(self._store.get(key, []))


class FakeEmbeddingClient:
    """固定向量的 fake embedding(长期记忆召回单测用).

    关键词 "报销" 命中向量 [1,0,0], 否则 [0,1,0]; 便于断言相似度排序.
    """

    def embed_one(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0] if "报销" in text else [0.0, 1.0, 0.0]


@dataclass
class FakeMemoryManager:
    """fake 记忆管理器: 记录观察/沉淀/召回调用, 固定返回召回文本.

    用于 ChatService 记忆集成单测, 避免依赖真实 Redis/PG/LLM.
    """

    interval: int = 5
    recalled_text: str = "- 用户偏好简洁回答"
    recalled: list[Any] = field(default_factory=list)  # 非空时 recall 返回(模拟命中)
    observed: list[tuple[Any, str, str]] = field(default_factory=list)
    sediment_calls: list[tuple[Any, str]] = field(default_factory=list)
    recall_calls: list[tuple[str, str]] = field(default_factory=list)

    async def observe(self, session_id: Any, role: str, content: str) -> None:
        self.observed.append((session_id, role, content))

    async def sediment(self, session_id: Any, user_id: str) -> int:
        self.sediment_calls.append((session_id, user_id))
        return 0

    async def recall(self, query: str, user_id: str, top_k: int | None = None) -> list[Any]:
        self.recall_calls.append((query, user_id))
        return list(self.recalled)

    def recall_text(self, hits: list[Any]) -> str:
        return self.recalled_text if hits else ""
