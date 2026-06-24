"""drop legacy checkpoints - 移除 P2 遗留的 checkpoints 表.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-07

P8(M7) 采用 LangGraph PostgresSaver 原生 checkpoint 表(thread_id/checkpoint_ns/
checkpoint_id/parent_checkpoint_id/checkpoint/metadata), 与 P2 建的 ORM checkpoints
表(id/agent_run_id/state)同名冲突且结构不兼容, 决策见 docs/adr/0004-langgraph-checkpoint.md.
本迁移删除旧表; LangGraph 侧表由 saver.setup() 自动创建, 不入 alembic 管理.
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_checkpoints_run", table_name="checkpoints")
    op.drop_table("checkpoints")


def downgrade() -> None:
    # 重建 P2 遗留表(供回滚; LangGraph 原生表由 saver.setup() 另行创建)
    op.create_table(
        "checkpoints",
        sa.Column("id", sa.String(length=128), nullable=False, comment="UUID"),
        sa.Column("agent_run_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_checkpoint_id", sa.String(length=128), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False, comment="序列化 AgentState"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_checkpoint_id"], ["checkpoints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_checkpoints_run", "checkpoints", ["agent_run_id"])
