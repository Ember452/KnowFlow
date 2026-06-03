"""文档与分块模型. Document / Chunk / DocumentIndex."""

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin, TimestampMixin, VectorField


class Document(Base, IDMixin, TimestampMixin):
    """上传的原始文档元信息."""

    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(512), nullable=False, comment="MinIO 对象 key")
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="pdf/docx/md/txt")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", comment="pending/indexing/ready/failed"
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="去重用")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Chunk(Base, IDMixin, TimestampMixin):
    """文档分块. 检索与索引的最小单元."""

    __tablename__ = "chunks"

    doc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(nullable=False, comment="文档内顺序")
    token_count: Mapped[int] = mapped_column(nullable=False, default=0)
    # P2 用 LargeBinary 存序列化向量, P7 评估迁移 pgvector VECTOR(1024)
    embedding: Mapped[bytes | None] = mapped_column(VectorField, nullable=True)

    __table_args__ = (
        Index("idx_chunks_doc", "doc_id"),
        Index("idx_chunks_index", "doc_id", "chunk_index"),
    )


class DocumentIndex(Base, IDMixin, TimestampMixin):
    """文档索引状态记录. 跟踪向量库/图谱/全文索引的构建情况."""

    __tablename__ = "document_indexes"

    doc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("chunks.id", ondelete="SET NULL"), nullable=True
    )
    index_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="vector/graph/bm25")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    __table_args__ = (Index("idx_doc_indexes_doc", "doc_id"),)
