"""对话服务单测 - 会话创建/复用、消息落库、检索接线、流式事件序列与异常兜底."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.core.exceptions import NotFoundError, ValidationError
from knowflow.db.repositories.session_repo import MessageRepo, TurnRepo
from knowflow.schemas.chat import ChatRequest
from knowflow.services.chat_service import ChatService
from tests.fakes import FakeChatLLM, FakeChunkWithScore, FakeRetriever

_CHUNK = FakeChunkWithScore(
    chunk_id=1, content="报销流程: 填写报销单并提交部门审批。", score=0.9, source="hybrid"
)


def _service(session: AsyncSession, llm: FakeChatLLM | None = None) -> ChatService:
    return ChatService(
        session=session,
        retriever=FakeRetriever(chunks=[_CHUNK]),
        llm=llm or FakeChatLLM(),
    )


async def test_chat_creates_session_and_persists(db_session: AsyncSession) -> None:
    """同步对话: 新建会话 → 消息/引用/轮次全部落库."""
    llm = FakeChatLLM()
    resp = await _service(db_session, llm).chat(
        ChatRequest(message="报销流程是什么?", user_id="u1")
    )

    assert resp.answer == llm.answer
    assert len(resp.citations) == 1
    assert resp.citations[0].chunk_id == 1
    assert resp.session_id.isdigit()

    messages = await MessageRepo(db_session).list_by_session(int(resp.session_id))
    assert [m.role for m in messages] == ["user", "assistant"]
    assert messages[1].content == llm.answer
    assert messages[1].citations["citations"][0]["chunk_id"] == 1

    turns = await TurnRepo(db_session).list_by_session(int(resp.session_id))
    assert len(turns) == 1


async def test_chat_reuses_session_with_history(db_session: AsyncSession) -> None:
    """多轮对话: 复用 session_id 时历史注入最近轮次."""
    llm = FakeChatLLM()
    service = _service(db_session, llm)
    first = await service.chat(ChatRequest(message="第一问", user_id="u1"))
    second = await service.chat(ChatRequest(message="第二问", session_id=first.session_id))

    assert second.session_id == first.session_id
    roles = [m["role"] for m in llm.last_messages]
    contents = [m["content"] for m in llm.last_messages]
    # 历史含上一轮的 user+assistant, 且当前问题在末尾
    assert roles[:2] == ["system", "user"]
    assert "第一问" in contents
    assert llm.answer in contents
    assert llm.last_messages[-1] == {"role": "user", "content": "第二问"}


async def test_chat_session_not_found(db_session: AsyncSession) -> None:
    """指定不存在的 session_id 抛 NotFoundError."""
    with pytest.raises(NotFoundError):
        await _service(db_session).chat(ChatRequest(message="hi", session_id="999"))


async def test_chat_invalid_session_id(db_session: AsyncSession) -> None:
    """非法 session_id 抛 ValidationError."""
    with pytest.raises(ValidationError):
        await _service(db_session).chat(ChatRequest(message="hi", session_id="abc"))


async def test_stream_events_sequence(db_session: AsyncSession) -> None:
    """流式事件序列: retrieval → token* → done, done 含引用与耗时."""
    events = []
    async for e in _service(db_session).stream_events(
        ChatRequest(message="报销流程", user_id="u1")
    ):
        events.append(e)

    types = [e["event"] for e in events]
    assert types[0] == "retrieval"
    assert "token" in types
    assert types[-1] == "done"

    retrieval = json.loads(events[0]["data"])
    assert retrieval["chunks"][0]["chunk_id"] == 1

    tokens = [json.loads(e["data"])["delta"] for e in events if e["event"] == "token"]
    assert "".join(tokens) == "这是来自KnowFlow的回复。"

    done = json.loads(events[-1]["data"])
    assert done["session_id"].isdigit()
    assert done["citations"][0]["chunk_id"] == 1
    assert done["latency_ms"] >= 0


async def test_stream_persists_messages_and_turn(db_session: AsyncSession) -> None:
    """流式结束: assistant 消息与轮次落库."""
    events = []
    async for e in _service(db_session).stream_events(ChatRequest(message="你好", user_id="u1")):
        events.append(e)

    done = json.loads(events[-1]["data"])
    messages = await MessageRepo(db_session).list_by_session(int(done["session_id"]))
    assert len(messages) == 2
    assert messages[1].role == "assistant"
    turns = await TurnRepo(db_session).list_by_session(int(done["session_id"]))
    assert len(turns) == 1


async def test_stream_error_event(db_session: AsyncSession) -> None:
    """LLM 流式异常: 最后事件为 error 且不抛给调用方."""
    llm = FakeChatLLM(raise_on_stream=True)
    events = []
    async for e in _service(db_session, llm).stream_events(ChatRequest(message="hi", user_id="u1")):
        events.append(e)

    assert events[-1]["event"] == "error"
    assert "failed" in json.loads(events[-1]["data"])["error"]
