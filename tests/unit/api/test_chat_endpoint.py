"""chat 端点单测 - 同步对话与 SSE 流式事件序列."""

import json

from fastapi.testclient import TestClient

from knowflow.api import deps
from tests.fakes import FakeChatLLM, FakeChunkWithScore, FakeRetriever

_CHUNK = FakeChunkWithScore(
    chunk_id=1, content="报销流程: 填写报销单并提交部门审批。", score=0.9, source="hybrid"
)


def _parse_sse(lines) -> list[tuple[str, str]]:
    """解析 TestClient 流式响应为 (event, data) 列表."""
    events: list[tuple[str, str]] = []
    event: str | None = None
    data_lines: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "" and event is not None:
            events.append((event, "\n".join(data_lines)))
            event = None
            data_lines = []
    if event is not None:
        events.append((event, "\n".join(data_lines)))
    return events


def test_chat_sync_returns_answer_and_citations(client: TestClient) -> None:
    """同步对话: 返回答案与检索引用."""
    deps.set_retriever(FakeRetriever(chunks=[_CHUNK]))
    resp = client.post("/api/v1/chat", json={"message": "报销流程是什么?", "user_id": "u1"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["answer"] == "这是来自 KnowFlow 的回复。"
    assert len(data["citations"]) == 1
    assert data["citations"][0]["chunk_id"] == 1
    assert data["session_id"].isdigit()


def test_chat_stream_events_sequence(client: TestClient) -> None:
    """流式对话: retrieval → token* → done 事件序列."""
    deps.set_retriever(FakeRetriever(chunks=[_CHUNK]))
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "报销流程"}) as resp:
        assert resp.status_code == 200
        events = _parse_sse(resp.iter_lines())

    types = [e[0] for e in events]
    assert types[0] == "retrieval"
    assert "token" in types
    assert types[-1] == "done"
    assert types.index("retrieval") < types.index("done")

    retrieval = json.loads(events[0][1])
    assert retrieval["chunks"][0]["chunk_id"] == 1

    tokens = [json.loads(e[1])["delta"] for e in events if e[0] == "token"]
    assert "".join(tokens) == "这是来自KnowFlow的回复。"

    done = json.loads(events[-1][1])
    assert done["session_id"].isdigit()
    assert done["citations"][0]["chunk_id"] == 1


# ── 工具链路(orchestrator 注入) ──


def test_chat_sync_with_tool_orchestrator(client: TestClient) -> None:
    """同步对话接入工具编排: 响应含 tool_calls(calculator 场景)."""
    from knowflow.services.tool_orchestrator import ToolCallRecord
    from tests.fakes import FakeToolOrchestrator

    fake = FakeToolOrchestrator(
        answer="2 的 10 次方是 1024。",
        tool_calls=[
            ToolCallRecord(
                tool_name="calculator",
                args={"expression": "2**10"},
                success=True,
                output=1024,
                latency_ms=3.0,
            )
        ],
    )
    deps.set_tool_orchestrator(fake)
    client.app.dependency_overrides[deps.get_tool_orchestrator] = lambda: (
        deps.get_tool_orchestrator()
    )

    resp = client.post("/api/v1/chat", json={"message": "帮我算 2 的 10 次方", "user_id": "u1"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["answer"] == "2 的 10 次方是 1024。"
    assert data["tool_calls"][0]["tool"] == "calculator"
    assert data["tool_calls"][0]["success"] is True


def test_chat_stream_with_tool_events(client: TestClient) -> None:
    """流式对话工具链路: retrieval → tool_start → tool_end → token → done."""
    from knowflow.services.tool_orchestrator import ToolCallRecord
    from tests.fakes import FakeToolOrchestrator

    fake = FakeToolOrchestrator(
        answer="计算结果: 1024",
        tool_calls=[
            ToolCallRecord(
                tool_name="calculator",
                args={"expression": "2**10"},
                success=True,
                output=1024,
                latency_ms=3.0,
            )
        ],
    )
    deps.set_tool_orchestrator(fake)
    client.app.dependency_overrides[deps.get_tool_orchestrator] = lambda: (
        deps.get_tool_orchestrator()
    )

    with client.stream(
        "POST", "/api/v1/chat/stream", json={"message": "帮我算 2 的 10 次方"}
    ) as resp:
        assert resp.status_code == 200
        events = _parse_sse(resp.iter_lines())

    types = [e[0] for e in events]
    assert types == ["retrieval", "tool_start", "tool_end", "token", "done"]
    tool_end = json.loads(events[2][1])
    assert tool_end["success"] is True
    assert json.loads(events[3][1])["delta"] == "计算结果: 1024"


def test_chat_stream_error_event(client: TestClient) -> None:
    """LLM 流式异常: 事件流以 error 结束."""
    deps.set_retriever(FakeRetriever(chunks=[_CHUNK]))
    client.app.dependency_overrides[deps.get_llm_dep] = lambda: FakeChatLLM(raise_on_stream=True)
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi"}) as resp:
        assert resp.status_code == 200
        events = _parse_sse(resp.iter_lines())

    assert events[-1][0] == "error"
    assert "failed" in json.loads(events[-1][1])["error"]
