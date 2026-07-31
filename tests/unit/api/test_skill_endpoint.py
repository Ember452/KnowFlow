"""Skill 端点单测 - 列表/启停.

GET /skills 返回全部 6 个 Skill(含运行时启停状态).
PUT /skills/{name}/toggle 切换启停; 不存在返回 404.
"""

from fastapi.testclient import TestClient


def test_list_skills(client: TestClient) -> None:
    """GET /skills 返回 6 个 Skill."""
    resp = client.get("/api/v1/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 6
    names = {s["name"] for s in data}
    expected = {
        "knowledge_qa",
        "document_summary",
        "data_analysis",
        "code_review",
        "report_writing",
    }
    assert expected <= names
    # 初始全部 enabled
    assert all(s["enabled"] for s in data)
    # SkillInfo 字段完整
    qa = next(s for s in data if s["name"] == "knowledge_qa")
    assert qa["domain"] == "skill_only"
    assert "retrieval_tool" in qa["tools"]


def test_toggle_skill_disable(client: TestClient) -> None:
    """PUT /skills/{name}/toggle 切换为 disabled."""
    resp = client.put("/api/v1/skills/knowledge_qa/toggle")
    assert resp.status_code == 200
    assert resp.json() == {"name": "knowledge_qa", "enabled": False}
    # 列表反映新状态
    data = client.get("/api/v1/skills").json()
    qa = next(s for s in data if s["name"] == "knowledge_qa")
    assert qa["enabled"] is False


def test_toggle_skill_reenable(client: TestClient) -> None:
    """再次 toggle 恢复 enabled."""
    client.put("/api/v1/skills/data_analysis/toggle")  # disable
    resp = client.put("/api/v1/skills/data_analysis/toggle")  # enable
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True


def test_toggle_missing_skill_404(client: TestClient) -> None:
    """toggle 不存在的 Skill 返回 404."""
    resp = client.put("/api/v1/skills/ghost/toggle")
    assert resp.status_code == 404
