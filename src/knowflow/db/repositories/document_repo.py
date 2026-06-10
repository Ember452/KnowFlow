"""Document / Chunk / DocumentIndex 数据访问层.

每个 repo 接收 AsyncSession, 由调用方管理事务. 返回 ORM 实例或列表.
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from knowflow.models.document import Chunk, Document, DocumentIndex


class DocumentRepo:
    """文档元信息 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        title: str,
        source_uri: str,
        file_type: str,
        size_bytes: int,
        user_id: str | None = None,
        content_hash: str | None = None,
        status: str = "pending",
    ) -> Document:
        """新建文档记录."""
        doc = Document(
            title=title,
            source_uri=source_uri,
            file_type=file_type,
            size_bytes=size_bytes,
            user_id=user_id,
            content_hash=content_hash,
            status=status,
        )
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get(self, doc_id: int) -> Document | None:
        """按主键查文档."""
        return await self.session.get(Document, doc_id)

    async def list_by_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Document]:
        """按用户列出文档, 按 id 倒序."""
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_by_user(self, user_id: str) -> int:
        """按用户统计文档总数(分页 total 用)."""
        stmt = select(func.count()).select_from(Document).where(Document.user_id == user_id)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def update_status(
        self, doc_id: int, status: str, error_message: str | None = None
    ) -> bool:
        """更新文档状态. 返回是否命中."""
        doc = await self.get(doc_id)
        if doc is None:
            return False
        doc.status = status
        if error_message is not None:
            doc.error_message = error_message
        await self.session.flush()
        return True

    async def delete(self, doc_id: int) -> bool:
        """删除文档(级联删除分块/索引). 返回是否命中."""
        doc = await self.get(doc_id)
        if doc is None:
            return False
        await self.session.delete(doc)
        await self.session.flush()
        return True

    async def find_by_content_hash(self, content_hash: str) -> Document | None:
        """按内容哈希查重."""
        stmt = select(Document).where(Document.content_hash == content_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class ChunkRepo:
    """分块 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        doc_id: int,
        content: str,
        chunk_index: int,
        token_count: int,
        embedding: bytes | None = None,
    ) -> Chunk:
        """新建分块."""
        chunk = Chunk(
            doc_id=doc_id,
            content=content,
            chunk_index=chunk_index,
            token_count=token_count,
            embedding=embedding,
        )
        self.session.add(chunk)
        await self.session.flush()
        await self.session.refresh(chunk)
        return chunk

    async def bulk_create(self, chunks: list[Chunk]) -> list[Chunk]:
        """批量建分块. 入参对象已构造好, 返回含 id 的对象列表."""
        self.session.add_all(chunks)
        await self.session.flush()
        for chunk in chunks:
            await self.session.refresh(chunk)
        return chunks

    async def get(self, chunk_id: int) -> Chunk | None:
        """按主键查分块."""
        return await self.session.get(Chunk, chunk_id)

    async def list_by_doc(self, doc_id: int) -> Sequence[Chunk]:
        """按文档列出全部分块, 按 chunk_index 升序."""
        stmt = select(Chunk).where(Chunk.doc_id == doc_id).order_by(Chunk.chunk_index.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_many(self, chunk_ids: Sequence[int]) -> Sequence[Chunk]:
        """按 id 列表批量获取, 保留输入顺序."""
        if not chunk_ids:
            return []
        stmt = select(Chunk).where(Chunk.id.in_(chunk_ids))
        result = await self.session.execute(stmt)
        by_id = {c.id: c for c in result.scalars().all()}
        return [by_id[cid] for cid in chunk_ids if cid in by_id]


class DocumentIndexRepo:
    """文档索引状态 CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        doc_id: int,
        index_type: str,
        status: str,
        chunk_id: int | None = None,
    ) -> DocumentIndex:
        """新建索引记录(简单 upsert: 先查后插, 不依赖 PG ON CONFLICT)."""
        stmt = select(DocumentIndex).where(
            DocumentIndex.doc_id == doc_id,
            DocumentIndex.index_type == index_type,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.status = status
            if chunk_id is not None:
                existing.chunk_id = chunk_id
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        idx = DocumentIndex(
            doc_id=doc_id,
            index_type=index_type,
            status=status,
            chunk_id=chunk_id,
        )
        self.session.add(idx)
        await self.session.flush()
        await self.session.refresh(idx)
        return idx

    async def list_by_doc(self, doc_id: int) -> Sequence[DocumentIndex]:
        """列出文档所有索引状态."""
        stmt = select(DocumentIndex).where(DocumentIndex.doc_id == doc_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
