"""add memory conflicts - 新增记忆冲突记录表(记忆治理留痕).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-09

记忆治理: 新记忆与存量记忆语义矛盾时写入 memory_conflicts 留痕,
供人工审查/仲裁; 新记忆照常生效(冲突不阻断写入).
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_conflicts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("new_content", sa.Text(), nullable=False, comment="新记忆内容"),
        sa.Column("old_memory_id", sa.BigInteger(), nullable=True),
        sa.Column("old_content", sa.Text(), nullable=False, comment="存量记忆内容"),
        sa.Column("reason", sa.String(length=255), nullable=False, comment="冲突判定原因"),
        sa.Column("status", sa.String(length=16), nullable=False, comment="pending/resolved"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["old_memory_id"], ["long_term_memories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_memory_conflicts_user", "memory_conflicts", ["user_id"])
    op.create_index("idx_memory_conflicts_status", "memory_conflicts", ["status"])


def downgrade() -> None:
    op.drop_index("idx_memory_conflicts_status", table_name="memory_conflicts")
    op.drop_index("idx_memory_conflicts_user", table_name="memory_conflicts")
    op.drop_table("memory_conflicts")
