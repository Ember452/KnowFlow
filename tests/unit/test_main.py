"""FastAPI 应用工厂与健康检查端点测试.

使用不带 context manager 的 TestClient, 不触发 lifespan(避免连接外部依赖);
lifespan 的容错行为在集成测试阶段(有容器依赖)验证.
"""

from fastapi.testclient import TestClient

from knowflow.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """存活探针: 进程存活即返回 ok, 不依赖外部服务."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_endpoint() -> None:
    """根路由返回应用名与版本."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == "KnowFlow"
    assert "version" in body


def test_openapi_docs_available() -> None:
    """OpenAPI 文档可访问."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger" in resp.text.lower()
