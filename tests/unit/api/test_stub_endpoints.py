"""占位端点单测 - chat/agent/skill/memory/trace/eval 返回 501 并标注里程碑."""

from fastapi.testclient import TestClient


def test_chat_stub_501(client: TestClient) -> None:
    resp = client.post("/api/v1/chat", json={"message": "hi"})
    assert resp.status_code == 501


def test_chat_stream_stub_501(client: TestClient) -> None:
    resp = client.post("/api/v1/chat/stream", json={"message": "hi"})
    assert resp.status_code == 501


def test_agent_stub_501(client: TestClient) -> None:
    assert client.get("/api/v1/agents/runs/1").status_code == 501


def test_skill_stub_501(client: TestClient) -> None:
    assert client.get("/api/v1/skills").status_code == 501
    assert client.put("/api/v1/skills/foo/toggle").status_code == 501


def test_memory_stub_501(client: TestClient) -> None:
    assert client.get("/api/v1/memory/u1").status_code == 501
    assert client.delete("/api/v1/memory/u1/1").status_code == 501


def test_trace_stub_501(client: TestClient) -> None:
    assert client.get("/api/v1/traces/1").status_code == 501
    assert client.post("/api/v1/traces/replay").status_code == 501


def test_eval_stub_501(client: TestClient) -> None:
    assert client.post("/api/v1/eval/run").status_code == 501
    assert client.get("/api/v1/eval/runs/1").status_code == 501
