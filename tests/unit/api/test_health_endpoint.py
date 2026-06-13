"""健康检查端点单测 - /healthz 存活 + /readyz 就绪(依赖探测)."""

from fastapi.testclient import TestClient


class _FakeMilvus:
    """可控的 Milvus 客户端 fake: ok=False 时 list_collections 抛连接异常."""

    def __init__(self, ok: bool = True) -> None:
        self._ok = ok

    def list_collections(self) -> list[str]:
        if not self._ok:
            raise ConnectionError("milvus down")
        return []


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


def test_readyz_milvus_ok_when_reachable(client: TestClient, monkeypatch) -> None:
    """Milvus 可连通时 readyz 报 ok(探测走真实 list_collections)."""
    monkeypatch.setattr("knowflow.db.milvus.get_milvus", lambda: _FakeMilvus(ok=True))
    resp = client.get("/api/v1/readyz")
    assert resp.json()["data"]["deps"]["milvus"] == "ok"


def test_readyz_milvus_fail_when_unreachable(client: TestClient, monkeypatch) -> None:
    """Milvus 服务不可达时 readyz 如实报 fail(不再仅凭客户端已创建误报)."""
    monkeypatch.setattr("knowflow.db.milvus.get_milvus", lambda: _FakeMilvus(ok=False))
    resp = client.get("/api/v1/readyz")
    assert resp.json()["data"]["deps"]["milvus"].startswith("fail")
