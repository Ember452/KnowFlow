"""报告端点单测 - 创建/进度/产物/发布(注入 fake 服务)."""

from typing import Any

from fastapi.testclient import TestClient

from knowflow.agents.report.models import (
    Chapter,
    Evidence,
    EvidenceSource,
    ReportResult,
    ReportSpec,
    ReviewResult,
)
from knowflow.api import deps
from knowflow.services.report_service import ReportTask


class _FakeService:
    """端点测试用 fake 报告服务(duck typing 对齐 ReportService 接口)."""

    def __init__(self) -> None:
        self.task = ReportTask(
            run_id="r1",
            query="总结制度",
            user_id="u1",
            status="completed",
            stage="done",
            detail="完成",
        )
        self.task.result = ReportResult(
            run_id="r1",
            spec=ReportSpec(title="报告", chapters=["一"]),
            evidence=[Evidence(source=EvidenceSource.KNOWLEDGE, content="证据1", title="文档1")],
            chapters=[Chapter(title="一", body="章节正文 [1]。")],
            review=ReviewResult(passed=True),
            references=["[1] 知识库文档: 文档1 (doc_id=1)"],
            markdown_path="/workspace/reports/r1.md",
        )

    async def create(
        self, query: str, user_id: str, session_id: int | str | None = None
    ) -> ReportTask:
        return ReportTask(run_id="new", query=query, user_id=user_id, session_id=session_id)

    def get(self, run_id: str) -> ReportTask | None:
        return self.task if run_id == "r1" else None

    def get_result(self, run_id: str) -> ReportResult | None:
        return self.task.result if run_id == "r1" else None

    async def publish(self, run_id: str) -> dict[str, Any]:
        if run_id == "r1":
            return {"published": True, "doc_url": "https://feishu.cn/docx/x", "message": "发布成功"}
        return {"published": False, "message": "报告任务不存在"}


def _inject(client: TestClient) -> None:
    """注入 fake 报告服务."""
    deps.set_report_service(_FakeService())
    client.app.dependency_overrides[deps.get_report_service] = lambda: deps.get_report_service()


def test_create_report_returns_task(client: TestClient) -> None:
    """POST /reports 创建任务并返回 run_id 与状态."""
    _inject(client)
    resp = client.post("/api/v1/reports", json={"query": "总结制度", "session_id": 1})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["run_id"] == "new"
    assert data["status"] == "running"
    assert data["query"] == "总结制度"


def test_create_report_rejects_short_query(client: TestClient) -> None:
    """query 过短触发 422 校验."""
    _inject(client)
    resp = client.post("/api/v1/reports", json={"query": "短"})
    assert resp.status_code == 422


def test_get_report_status(client: TestClient) -> None:
    """GET /reports/{id} 返回任务状态与进度."""
    _inject(client)
    resp = client.get("/api/v1/reports/r1")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert data["markdown_path"] == "/workspace/reports/r1.md"


def test_get_report_not_found(client: TestClient) -> None:
    """不存在的任务返回 404."""
    _inject(client)
    resp = client.get("/api/v1/reports/missing")
    assert resp.status_code == 404


def test_get_report_result(client: TestClient) -> None:
    """GET /reports/{id}/result 返回完整产物."""
    _inject(client)
    resp = client.get("/api/v1/reports/r1/result")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["title"] == "报告"
    assert data["chapters"][0]["body"] == "章节正文 [1]。"
    assert data["evidence"][0]["source"] == "knowledge"
    assert data["review_passed"] is True
    assert data["references"] == ["[1] 知识库文档: 文档1 (doc_id=1)"]


def test_publish_report(client: TestClient) -> None:
    """POST /reports/{id}/publish 返回发布结果与文档链接."""
    _inject(client)
    resp = client.post("/api/v1/reports/r1/publish")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["published"] is True
    assert data["doc_url"] == "https://feishu.cn/docx/x"


def test_publish_report_unknown(client: TestClient) -> None:
    """发布不存在的任务返回可读提示."""
    _inject(client)
    resp = client.post("/api/v1/reports/missing/publish")
    assert resp.status_code == 200
    assert resp.json()["data"]["published"] is False


def test_report_service_unavailable_returns_503(client: TestClient) -> None:
    """报告服务不可用(None)时返回 503."""
    deps.set_report_service(None)
    client.app.dependency_overrides[deps.get_report_service] = lambda: deps.get_report_service()
    resp = client.post("/api/v1/reports", json={"query": "总结制度"})
    assert resp.status_code == 503
