"""add memory embedding_vec - 长期记忆 pgvector 向量列(去重 top-N 检索).

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-15

去重写入性能改造: 开启 pgvector 扩展, long_term_memories 增加
embedding_vec vector(1024) 列 + HNSW 余弦索引, 写入去重改为数据库
近似最近邻检索(只取少量候选, 再精确校验), 不再全量拉取用户记忆.
存量数据不在此迁移回填(避免坏数据阻塞迁移), 由
scripts/backfill_memory_vectors.py 一次性回填; 回填前应用层自动降级
Python 全量扫描, 功能不受影响.
"""

import logging

import sqlalchemy as sa
from alembic import op

logger = logging.getLogger("alembic.runtime.migration")

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    try:
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception:
        # 无扩展创建权限(托管 PG 常见): 跳过向量列, 应用层自动降级 Python 去重
        logger.warning(
            "0004 skip pgvector: CREATE EXTENSION vector failed, fallback to python dedup"
        )
        return
    op.execute(sa.text("ALTER TABLE long_term_memories ADD COLUMN embedding_vec vector(1024)"))
    op.execute(
        sa.text(
            "CREATE INDEX idx_memories_user_vec ON long_term_memories "
            "USING hnsw (embedding_vec vector_cosine_ops)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP INDEX IF EXISTS idx_memories_user_vec"))
        op.execute(sa.text("ALTER TABLE long_term_memories DROP COLUMN IF EXISTS embedding_vec"))
