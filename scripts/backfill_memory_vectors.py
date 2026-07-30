"""存量长期记忆 embedding_vec 回填脚本.

背景: 迁移 0004 只新增 embedding_vec 列(不做数据回填, 避免坏数据阻塞迁移);
本脚本把已有 embedding(LargeBinary JSON 序列化)反序列化后写入 embedding_vec.
回填完成前, 含存量数据的用户去重自动降级 Python 全量扫描(功能不受影响);
回填完成后, 去重 SQL top-N 路径对全部用户生效.

用法:
    uv run python scripts/backfill_memory_vectors.py            # 全量回填
    uv run python scripts/backfill_memory_vectors.py --batch 1000  # 每批条数

依赖: 真实 PostgreSQL + pgvector 扩展(迁移 0004 已创建).
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# 将 src 加入 sys.path, 支持 `python scripts/backfill_memory_vectors.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from knowflow.core.config import get_settings  # noqa: E402
from knowflow.core.logging import get_logger, setup_logging  # noqa: E402
from knowflow.models.memory import LongTermMemory  # noqa: E402

logger = get_logger(__name__)


def _parse_embedding(raw: bytes | None) -> list[float] | None:
    """反序列化存量向量; 无值/损坏/类型不符返回 None(跳过该行)."""
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, list):
            return None
        return [float(x) for x in data]
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


async def _backfill(batch: int = 500) -> int:
    """分批回填: embedding 非空且 embedding_vec 为空的行, 返回回填条数."""
    settings = get_settings()
    engine = create_async_engine(settings.postgres_dsn, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    updated = 0
    try:
        async with factory() as session:
            while True:
                rows = (
                    (
                        await session.execute(
                            select(LongTermMemory)
                            .where(
                                LongTermMemory.embedding.is_not(None),
                                LongTermMemory.embedding_vec.is_(None),
                            )
                            .limit(batch)
                        )
                    )
                    .scalars()
                    .all()
                )
                if not rows:
                    break
                for m in rows:
                    vec = _parse_embedding(m.embedding)
                    if vec:
                        m.embedding_vec = vec
                        updated += 1
                    else:
                        logger.warning("backfill.skip_bad_row", memory_id=int(m.id))
                await session.flush()
                await session.commit()
                logger.info("backfill.batch_done", batch=len(rows), total=updated)
    finally:
        await engine.dispose()
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="长期记忆 embedding_vec 存量回填")
    parser.add_argument("--batch", type=int, default=500, help="每批处理条数")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    setup_logging()
    try:
        updated = await _backfill(batch=args.batch)
    except Exception as exc:
        logger.error(
            "backfill.failed",
            error=str(exc),
            hint="请确认 PG 可达且已应用迁移 0004(CREATE EXTENSION vector)",
        )
        return 1
    logger.info("backfill.done", updated=updated)
    return 0


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(_run(args)))
