"""工具治理端点单测 - GET /tools/stats.

空 orchestrator 时返回治理基线(总量/可见数/Schema Token/域分布);
注入带 ToolMetrics 的 fake orchestrator 后返回运行时聚合指标.
"""

from fastapi.testclient import TestClient

from knowflow.api import deps
from knowflow.tools.metrics import ToolMetrics


def test_stats_returns_governance_baseline(client: TestClient) -> None:
    """orchestrator 未就绪时返回基线统计, 运行时指标为空."""
    resp = client.get("/api/v1/tools/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tools"] >= 4
    assert data["visible_tools"] > 0
    assert data["schema_tokens"] > 0
    assert set(data["domain_breakdown"]) == {
        "direct",
        "skill_only",
        "subagent_only",
        "internal",
    }
    assert sum(data["domain_breakdown"].values()) == data["total_tools"]
    assert data["metrics"] == []
    assert data["accuracy"] == 0.0


def test_stats_aggregates_runtime_calls(client: TestClient) -> None:
    """注入带调用记录的 fake orchestrator 后, 逐工具指标与 FC 准确率生效."""

    class FakeOrchestrator:
        def __init__(self) -> None:
            self.metrics = ToolMetrics()

    fake = FakeOrchestrator()
    fake.metrics.record_call("calculator", success=True, tokens=120, latency_ms=10.0)
    fake.metrics.record_call("calculator", success=False, tokens=90, latency_ms=15.0)
    fake.metrics.record_call("retrieval_tool", success=True, tokens=300, latency_ms=40.0)
    fake.metrics.snapshot(visible_count=6, schema_tokens=800, fc_correct=True)

    deps.set_tool_orchestrator(fake)
    client.app.dependency_overrides[deps.get_tool_orchestrator] = lambda: (
        deps.get_tool_orchestrator()
    )

    resp = client.get("/api/v1/tools/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["accuracy"] == 1.0

    by_name = {m["tool"]: m for m in data["metrics"]}
    assert set(by_name) == {"calculator", "retrieval_tool"}
    # 调用次数降序: calculator(2) 排在 retrieval_tool(1) 前
    assert [m["tool"] for m in data["metrics"]] == ["calculator", "retrieval_tool"]
    calc = by_name["calculator"]
    assert calc["calls"] == 2
    assert calc["success_rate"] == 0.5
    assert calc["avg_latency_ms"] == 12.5
    assert calc["token_count"] == 210
    assert calc["domain"] != "unknown"
    assert by_name["retrieval_tool"]["calls"] == 1
