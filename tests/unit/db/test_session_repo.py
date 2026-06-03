"""SessionRepo / MessageRepo / TurnRepo 单测."""

import pytest

from knowflow.db.repositories.session_repo import MessageRepo, SessionRepo, TurnRepo


@pytest.mark.asyncio
async def test_session_create_and_get(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = SessionRepo(db_session)
    sess = await repo.create(user_id="u1", title="t1")
    await db_session.commit()

    fetched = await repo.get(sess.id)
    assert fetched is not None
    assert fetched.user_id == "u1"
    assert fetched.status == "active"


@pytest.mark.asyncio
async def test_session_list_by_user_orders_desc(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = SessionRepo(db_session)
    s1 = await repo.create(user_id="u1")
    s2 = await repo.create(user_id="u1")
    await db_session.commit()

    sessions = await repo.list_by_user("u1")
    assert [s.id for s in sessions] == [s2.id, s1.id]


@pytest.mark.asyncio
async def test_session_update_status(db_session) -> None:  # type: ignore[no-untyped-def]
    repo = SessionRepo(db_session)
    sess = await repo.create(user_id="u1")
    await db_session.commit()

    ok = await repo.update_status(sess.id, "closed")
    assert ok is True
    fetched = await repo.get(sess.id)
    assert fetched is not None
    assert fetched.status == "closed"

    assert await repo.update_status(99999, "closed") is False


@pytest.mark.asyncio
async def test_message_create_and_list(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    msg_repo = MessageRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    await db_session.commit()

    m1 = await msg_repo.create(session_id=sess.id, role="user", content="你好", tokens=2)
    m2 = await msg_repo.create(session_id=sess.id, role="assistant", content="您好", tokens=2)
    await db_session.commit()

    msgs = await msg_repo.list_by_session(sess.id)
    assert [m.id for m in msgs] == [m1.id, m2.id]
    assert msgs[0].role == "user"
    assert msgs[1].role == "assistant"


@pytest.mark.asyncio
async def test_message_citations_json(db_session) -> None:  # type: ignore[no-untyped-def]
    """citations 字段(JSON)在 SQLite 上应能正常存取."""
    sess_repo = SessionRepo(db_session)
    msg_repo = MessageRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    await db_session.commit()

    citations = {"chunks": [1, 2, 3], "score": 0.95}
    msg = await msg_repo.create(
        session_id=sess.id,
        role="assistant",
        content="答案",
        tokens=1,
        citations=citations,
    )
    await db_session.commit()

    fetched = await msg_repo.get(msg.id)
    assert fetched is not None
    assert fetched.citations == citations


@pytest.mark.asyncio
async def test_turn_create_and_list(db_session) -> None:  # type: ignore[no-untyped-def]
    sess_repo = SessionRepo(db_session)
    msg_repo = MessageRepo(db_session)
    turn_repo = TurnRepo(db_session)
    sess = await sess_repo.create(user_id="u1")
    user_msg = await msg_repo.create(session_id=sess.id, role="user", content="q", tokens=1)
    assistant_msg = await msg_repo.create(
        session_id=sess.id, role="assistant", content="a", tokens=1
    )
    await db_session.commit()

    turn = await turn_repo.create(
        session_id=sess.id,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        trace_id="trace-1",
    )
    await db_session.commit()

    turns = await turn_repo.list_by_session(sess.id)
    assert len(turns) == 1
    assert turns[0].id == turn.id
    assert turns[0].trace_id == "trace-1"
