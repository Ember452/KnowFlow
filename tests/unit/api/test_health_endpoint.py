"""健康检查端点单测 - /healthz 存活 + /readyz 就绪(依赖探测)."""

from fastapi.testclient import TestClient


def test_healthz_ok(client: TestClient) -> None:
    """/healthz 进程存活即 ok."""
    resp = client.get("/api/v1/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["status"] == "ok"


def test_readyz_reports_deps(client: TestClient) -> None:
    """/readyz 返回依赖探测结果(测试环境无真实依赖, 多为 degraded)."""
    resp = client.get("/api/v1/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert "deps" in body["data"]
    # 测试环境未初始化外部依赖, 至少能返回结构
    assert "postgres" in body["data"]["deps"]
