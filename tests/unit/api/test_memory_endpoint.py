"""记忆端点单测 - 列表/删除/手动沉淀."""

from fastapi.testclient import TestClient


def _create_session_with_preference(client: TestClient) -> str:
    """创建会话并留下高价值偏好消息(经 chat 端点落短期记忆), 返回 session_id."""
    resp = client.post(
        "/api/v1/chat",
        json={"message": "请记住我喜欢用 Markdown 写文档", "user_id": "u1"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def test_sediment_then_list(client: TestClient) -> None:
    """手动沉淀: 会话短期记忆筛选后写入长期, 列表可见."""
    sid = _create_session_with_preference(client)

    resp = client.post("/api/v1/memory/u1/sediment", json={"session_id": int(sid)})
    assert resp.status_code == 200, resp.text
    assert resp.json()["saved"] == 1

    memories = client.get("/api/v1/memory/u1").json()
    assert len(memories) == 1
    assert memories[0]["content"] == "请记住我喜欢用 Markdown 写文档"
    assert memories[0]["importance"] == 9.0  # 规则打分: 偏好类高置信


def test_sediment_empty_session_saves_nothing(client: TestClient) -> None:
    """无高价值消息的会话沉淀结果为 0."""
    resp = client.post("/api/v1/memory/u2/sediment", json={"session_id": 999})
    assert resp.status_code == 200
    assert resp.json()["saved"] == 0


# 同一偏好在两个会话各沉淀一次, 长期记忆只保留一条(去重合并)
def test_sediment_dedup_same_preference_across_sessions(client: TestClient) -> None:
    """同一偏好跨会话重复沉淀: 合并为一条, 不冗余存储."""
    sid1 = _create_session_with_preference(client)
    sid2 = _create_session_with_preference(client)

    assert (
        client.post("/api/v1/memory/u1/sediment", json={"session_id": int(sid1)}).json()["saved"]
        == 1
    )
    assert (
        client.post("/api/v1/memory/u1/sediment", json={"session_id": int(sid2)}).json()["saved"]
        == 1
    )

    memories = client.get("/api/v1/memory/u1").json()
    assert len(memories) == 1
    assert memories[0]["content"] == "请记住我喜欢用 Markdown 写文档"


def test_delete_memory(client: TestClient) -> None:
    """删除单条记忆; 重复删除返回 404."""
    sid = _create_session_with_preference(client)
    client.post("/api/v1/memory/u1/sediment", json={"session_id": int(sid)})
    memory_id = client.get("/api/v1/memory/u1").json()[0]["id"]

    resp = client.delete(f"/api/v1/memory/u1/{memory_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True
    assert client.get("/api/v1/memory/u1").json() == []

    assert client.delete(f"/api/v1/memory/u1/{memory_id}").status_code == 404


def test_memory_list_empty_for_unknown_user(client: TestClient) -> None:
    assert client.get("/api/v1/memory/nobody").json() == []
