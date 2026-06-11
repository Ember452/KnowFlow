"""文档端点单测 - 上传/列表/删除/重建索引 全链路(依赖已覆盖为 fake)."""

from fastapi.testclient import TestClient


def _upload(client: TestClient, name: str = "demo.md", content: bytes = b"# hello\nworld") -> dict:
    """便利: 上传一个文件, 返回响应 json."""
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": (name, content, "text/markdown")},
        headers={"X-User-Id": "u1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_upload_returns_pending(client: TestClient) -> None:
    """上传成功返回 pending 状态与 doc_id, 并投递索引任务."""
    body = _upload(client)
    data = body["data"]
    assert data["status"] == "pending"
    assert data["doc_id"] > 0
    assert data["duplicated"] is False


def test_upload_dedup(client: TestClient) -> None:
    """同内容二次上传命中秒传, duplicated=True."""
    first = _upload(client, content=b"same content")
    second = _upload(client, content=b"same content")
    assert first["data"]["duplicated"] is False
    assert second["data"]["duplicated"] is True
    assert second["data"]["doc_id"] == first["data"]["doc_id"]


def test_upload_rejects_bad_type(client: TestClient) -> None:
    """不支持的文件类型返回 422(ValidationError)."""
    resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("bad.exe", b"MZ", "application/octet-stream")},
        headers={"X-User-Id": "u1"},
    )
    assert resp.status_code == 422


def test_list_documents(client: TestClient) -> None:
    """列表返回分页结构, total 与上传数一致."""
    _upload(client, content=b"a")
    _upload(client, content=b"b")
    resp = client.get("/api/v1/documents", params={"limit": 10}, headers={"X-User-Id": "u1"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_delete_document(client: TestClient) -> None:
    """删除后列表不再包含该文档."""
    up = _upload(client, content=b"to-delete")
    doc_id = up["data"]["doc_id"]
    resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True
    # 列表中不再有
    lst = client.get("/api/v1/documents", headers={"X-User-Id": "u1"}).json()["data"]
    assert all(item["id"] != doc_id for item in lst["items"])


def test_delete_not_found(client: TestClient) -> None:
    """删除不存在文档返回 404."""
    resp = client.delete("/api/v1/documents/99999")
    assert resp.status_code == 404


def test_reindex_document(client: TestClient) -> None:
    """重建索引置 pending 并投递任务."""
    up = _upload(client, content=b"reindex-me")
    doc_id = up["data"]["doc_id"]
    resp = client.post(f"/api/v1/documents/{doc_id}/reindex")
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending"
