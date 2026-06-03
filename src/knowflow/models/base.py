"""ORM 基类与公共混入.

- Base: SQLAlchemy 2.0 声明式基类
- IDMixin: BIGINT 自增主键
- TimestampMixin: created_at / updated_at(均为 TIMESTAMPTZ)
- JSONBType: PG 用 JSONB, SQLite 用 JSON(单测兼容)
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, LargeBinary, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, TypeDecorator


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类."""


class JSONBType(TypeDecorator):
    """跨数据库 JSON 类型: PG 用 JSONB, 其他(SQLite)用 JSON.

    让 repo 单测可在 SQLite 上运行, 同时生产 PG 享受 JSONB 索引/查询优势.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class IDMixin:
    """BIGINT 自增主键. SQLite 降级为 Integer 以支持 autoincrement."""

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


class TimestampMixin:
    """created_at / updated_at 时间戳, 统一 TIMESTAMPTZ."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# 向量字段类型别名: P2 用 LargeBinary 存序列化向量, P7 评估迁移 pgvector VECTOR(1024)
VectorField = LargeBinary


__all__ = [
    "Base",
    "IDMixin",
    "JSONBType",
    "TimestampMixin",
    "VectorField",
]
