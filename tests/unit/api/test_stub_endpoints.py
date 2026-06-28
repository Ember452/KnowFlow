"""占位端点单测 - P10(M8) 后全部端点已实现, 无 stub 残留.

chat/skill/memory/agent/trace/eval 端点已分别由 P5-P10 实现,
对应测试见 tests/unit/api/test_*.py. 本文件保留用于标记占位端点清零.
"""

from fastapi.testclient import TestClient


def test_no_stub_endpoints_remain(client: TestClient) -> None:
    """trace/eval 端点已实现: 不再返回 501, 而是正常的 404/422 等业务码."""
    # trace: 无记录会话返回 404(而非 501)
    assert client.get("/api/v1/traces/99999").status_code == 404
    # eval: 缺请求体返回 422(而非 501)
    assert client.post("/api/v1/eval/run").status_code == 422
