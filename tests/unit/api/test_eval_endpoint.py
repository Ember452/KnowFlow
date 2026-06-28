"""Eval 端点单测 - 静态评测触发/落库/查询(P10 实现)."""

from fastapi.testclient import TestClient


def test_eval_run_retrieval(client: TestClient) -> None:
    """POST /eval/run: 检索评测落库并返回汇总指标."""
    resp = client.post(
        "/api/v1/eval/run", json={"dataset": "retrieval_eval", "mode": "static", "top_k": 5}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["dataset"] == "retrieval_eval"
    assert "recall@5" in data["summary"]
    assert len(data["results"]) == 50  # 评测集 50 条


def test_eval_run_qa(client: TestClient) -> None:
    """POST /eval/run: QA 评测(要点命中率)."""
    resp = client.post("/api/v1/eval/run", json={"dataset": "knowledge_qa_eval", "mode": "static"})
    assert resp.status_code == 200
    data = resp.json()
    assert "keypoint_hit_rate" in data["summary"]
    assert len(data["results"]) == 60  # QA 评测集 60 条


def test_eval_run_unknown_dataset(client: TestClient) -> None:
    """未知评测集返回 400."""
    resp = client.post("/api/v1/eval/run", json={"dataset": "nope", "mode": "static"})
    assert resp.status_code == 400


def test_eval_run_real_mode_rejected(client: TestClient) -> None:
    """真实模式在端点层拒绝(指引走离线脚本)."""
    resp = client.post("/api/v1/eval/run", json={"dataset": "retrieval_eval", "mode": "real"})
    assert resp.status_code == 400


def test_eval_run_query_back(client: TestClient) -> None:
    """GET /eval/runs/{run_id}: 查询落库的评测结果."""
    resp = client.post("/api/v1/eval/run", json={"dataset": "retrieval_eval", "mode": "static"})
    run_id = resp.json()["run_id"]
    resp2 = client.get(f"/api/v1/eval/runs/{run_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["run_id"] == run_id
    assert data["summary"]  # 汇总指标可读回


def test_eval_run_not_found(client: TestClient) -> None:
    """不存在的评测运行返回 404."""
    resp = client.get("/api/v1/eval/runs/99999")
    assert resp.status_code == 404
