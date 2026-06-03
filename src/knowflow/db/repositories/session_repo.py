"""Session / Message / Turn 数据访问层."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.models.session import Message, Session, Turn


class SessionRepo:
    """会话 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, *, user_id: str | None = None, title: str | None = None, status: str = "active"
    ) -> Session:
        """新建会话."""
        sess = Session(user_id=user_id, title=title, status=status)
        self.session.add(sess)
        await self.session.flush()
        await self.session.refresh(sess)
        return sess

    async def get(self, session_id: int) -> Session | None:
        """按主键查会话."""
        return await self.session.get(Session, session_id)

    async def list_by_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Session]:
        """按用户列出会话, 按 id 倒序."""
        stmt = (
            select(Session)
            .where(Session.user_id == user_id)
            .order_by(Session.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_status(self, session_id: int, status: str) -> bool:
        """更新会话状态(active/closed/archived). 返回是否命中."""
        sess = await self.get(session_id)
        if sess is None:
            return False
        sess.status = status
        await self.session.flush()
        return True


class MessageRepo:
    """消息 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        tokens: int = 0,
        citations: dict | None = None,
    ) -> Message:
        """新建消息. role: user/assistant/system/tool."""
        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
            tokens=tokens,
            citations=citations,
        )
        self.session.add(msg)
        await self.session.flush()
        await self.session.refresh(msg)
        return msg

    async def get(self, message_id: int) -> Message | None:
        """按主键查消息."""
        return await self.session.get(Message, message_id)

    async def list_by_session(self, session_id: int, *, limit: int = 100) -> Sequence[Message]:
        """按会话列出消息, 按 id 升序(时间序)."""
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class TurnRepo:
    """对话轮次 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        session_id: int,
        user_message_id: int,
        assistant_message_id: int | None = None,
        trace_id: str | None = None,
    ) -> Turn:
        """新建对话轮次."""
        turn = Turn(
            session_id=session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            trace_id=trace_id,
        )
        self.session.add(turn)
        await self.session.flush()
        await self.session.refresh(turn)
        return turn

    async def list_by_session(self, session_id: int) -> Sequence[Turn]:
        """按会话列出轮次, 按 id 升序."""
        stmt = select(Turn).where(Turn.session_id == session_id).order_by(Turn.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
