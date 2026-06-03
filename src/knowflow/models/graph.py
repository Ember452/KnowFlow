"""图谱模型. Entity / EntityAlias / Relation - GraphRAG 实体关系存储.

与设计文档 3.4 一致, 这三张表只有 created_at(无 updated_at), 不使用 TimestampMixin.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from knowflow.models.base import Base, IDMixin


class Entity(Base, IDMixin):
    """实体. 从 chunk 中 LLM 抽取的命名实体."""

    __tablename__ = "entities"

    doc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="person/org/...")
    normalized: Mapped[str] = mapped_column(String(255), nullable=False, comment="归一化名称")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_entities_normalized", "normalized"),
        Index("idx_entities_chunk", "chunk_id"),
    )


class EntityAlias(Base, IDMixin):
    """实体别名. 同义词/别名映射, 用于实体归一."""

    __tablename__ = "entity_aliases"

    entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("entity_id", "alias", name="uq_entity_alias"),)


class Relation(Base, IDMixin):
    """关系. 实体间的有向边, 一跳扩展的核心."""

    __tablename__ = "relations"

    doc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    target_entity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="belongs_to/related_to/part_of..."
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_relations_source", "source_entity_id"),
        Index("idx_relations_target", "target_entity_id"),
    )
