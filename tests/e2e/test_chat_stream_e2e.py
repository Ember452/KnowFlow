"""对话流式端到端测试 - 真实 LLM 跑通完整 QA 流.

依赖: 真实 LLM API Key(settings.llm_api_key 非空), 无 Key 时整模块跳过.
通过 client fixture 注入 SQLite + FakeRetriever(固定知识片段), 仅 LLM 走真实 ChatOpenAI.
断言事件序列 retrieval → token* → done 且回答非空, 并打印首 token 耗时(供 docs/benchmarks 记录).
"""

import json
import time

import pytest
from fastapi.testclient import TestClient

from knowflow.api import deps
from knowflow.core.config import get_settings
from tests.fakes import FakeChunkWithScore, FakeRetriever

pytestmark = pytest.mark.skipif(
    not get_settings().llm_api_key,
    reason="需要真实 LLM API Key 才能跑端到端对话流",
)

_CHUNK = FakeChunkWithScore(
    chunk_id=1,
    content="KnowFlow 报销流程: 员工填写报销单, 提交部门审批后由财务放款。",
    score=0.95,
    source="hybrid",
)


def _parse_sse(lines) -> list[tuple[str, str]]:
    """解析流式响应为 (event, data) 列表."""
    events: list[tuple[str, str]] = []
    event: str | None = None
    data_lines: list[str] = []
    for raw in lines:
        line = raw.strip()
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "" and event is not None:
            events.append((event, "\n".join(data_lines)))
            event = None
            data_lines = []
    if event is not None:
        events.append((event, "\n".join(data_lines)))
    return events


def test_chat_stream_real_llm(client: TestClient) -> None:
    """真实模型流式 QA: 事件序列完整 + 回答非空 + 记录首 token 耗时."""
    deps.set_retriever(FakeRetriever(chunks=[_CHUNK]))
    # 移除 fake LLM 覆盖, 走真实 ChatOpenAI 单例
    client.app.dependency_overrides.pop(deps.get_llm_dep, None)

    start = time.perf_counter()
    with client.stream(
        "POST", "/api/v1/chat/stream", json={"message": "公司报销流程是什么?", "user_id": "e2e"}
    ) as resp:
        assert resp.status_code == 200
        events = _parse_sse(resp.iter_lines())

    types = [e[0] for e in events]
    assert types[0] == "retrieval"
    assert "token" in types
    assert types[-1] == "done", f"事件流未以 done 结束: {types}"

    # 首 token 耗时(近似: 从请求发起算起), 目标 < 800ms, 实测记录到 docs/benchmarks
    first_token_ms = (time.perf_counter() - start) * 1000
    print(f"\n[e2e] first_token_ms={first_token_ms:.0f}")

    answer = "".join(json.loads(e[1])["delta"] for e in events if e[0] == "token")
    assert answer.strip(), "回答内容为空"

    done = json.loads(events[-1][1])
    assert isinstance(done["session_id"], int)
    assert done["citations"][0]["chunk_id"] == 1
