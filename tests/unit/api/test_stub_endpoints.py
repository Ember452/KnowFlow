"""占位端点单测 - agent/trace/eval 返回 501 并标注里程碑.

chat/skill/memory 端点已分别由 P5(M4)/P6(M5)/P7(M6) 实现, 见对应测试文件.
"""

from fastapi.testclient import TestClient


def test_agent_stub_501(client: TestClient) -> None:
    assert client.get("/api/v1/agents/runs/1").status_code == 501


def test_trace_stub_501(client: TestClient) -> None:
    assert client.get("/api/v1/traces/1").status_code == 501
    assert client.post("/api/v1/traces/replay").status_code == 501


def test_eval_stub_501(client: TestClient) -> None:
    assert client.post("/api/v1/eval/run").status_code == 501
    assert client.get("/api/v1/eval/runs/1").status_code == 501
