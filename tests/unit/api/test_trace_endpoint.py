"""Trace 端点单测 - Trace 树 / stats 聚合 / replay(P10 实现)."""

import asyncio

from fastapi.testclient import TestClient

from knowflow.db.repositories.agent_repo import AgentRunRepo
from knowflow.db.repositories.session_repo import SessionRepo
from knowflow.models.tool import ToolCall
from knowflow.observability.collector import SpanCollector
from knowflow.observability.span import SpanType
from knowflow.observability.store import TraceStore
from knowflow.observability.tracer import Tracer


def _seed_trace(api_session_factory: object) -> int:
    """种子数据: 会话 + 主 run + 嵌套 span 树(返回 session_id)."""

    async def seed() -> int:
        async with api_session_factory() as session:  # type: ignore[attr-defined]
            sess = await SessionRepo(session).create(user_id="u1")
            await session.commit()
            sid = int(sess.id)
            await AgentRunRepo(session).create(session_id=sid, agent_type="main")
            await session.commit()

            # 构造 trace: root → retrieval → tool_call
            store = TraceStore(session)
            collector = SpanCollector(store)
            tracer = Tracer(collector, trace_id_factory=lambda: "tr-api")
            await tracer.start_trace(session_id=sid)
            retrieval = await tracer.start_span(
                SpanType.RETRIEVAL, "hybrid_retrieve", input={"query": "报销流程"}
            )
            await tracer.end_span(retrieval, {"chunks": 3})
            await tracer.end_trace()
            await collector.flush()
            # 一条工具调用记录(stats 用)
            session.add(
                ToolCall(tool_name="calculator", success=True, latency_ms=10, token_usage=0)
            )
            await session.commit()
            return sid

    return asyncio.run(seed())


def test_trace_tree(client: TestClient, api_session_factory: object) -> None:
    """GET /traces/{session_id}: 嵌套树含 root/retrieval, 层级正确."""
    sid = _seed_trace(api_session_factory)
    resp = client.get(f"/api/v1/traces/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == sid
    assert len(data["roots"]) == 1
    root = data["roots"][0]
    assert root["span_type"] == "root"
    assert len(root["children"]) == 1
    assert root["children"][0]["span_type"] == "retrieval"
    assert root["children"][0]["input"] == {"query": "报销流程"}
    assert root["children"][0]["latency_ms"] >= 0


def test_trace_tree_not_found(client: TestClient) -> None:
    """无 trace 的会话返回 404."""
    resp = client.get("/api/v1/traces/99999")
    assert resp.status_code == 404


def test_trace_stats(client: TestClient, api_session_factory: object) -> None:
    """GET /traces/stats: 聚合对话数/工具成功率."""
    _seed_trace(api_session_factory)
    resp = client.get("/api/v1/traces/stats?hours=24")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dialogs"] >= 1
    assert data["span_counts"]["retrieval"] >= 1
    assert data["tool_calls"] >= 1
    assert data["tool_success_rate"] == 100.0


def test_trace_stats_default_hours(client: TestClient) -> None:
    """stats 不带参数时默认 24 小时."""
    resp = client.get("/api/v1/traces/stats")
    assert resp.status_code == 200
    assert resp.json()["hours"] == 24


def test_replay_without_main_run_404(client: TestClient, api_session_factory: object) -> None:
    """会话无主 Agent run 时 replay 返回 404."""
    resp = client.post("/api/v1/traces/replay", json={"session_id": 99999, "checkpoint_id": None})
    assert resp.status_code == 404  # 无主 run


def test_replay_request_validation(client: TestClient) -> None:
    """非法请求体(缺 session_id)返回 422."""
    resp = client.post("/api/v1/traces/replay", json={})
    assert resp.status_code == 422
