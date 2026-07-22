"""数据库初始化脚本.

职责:
1. 创建 PostgreSQL 数据库(若不存在, 针对 dev 环境)
2. 执行 alembic upgrade head 应用最新迁移
3. 可选: 创建默认 eval_dataset 占位

用法:
    uv run python scripts/init_db.py              # 应用迁移到 head
    uv run python scripts/init_db.py --check      # 仅打印当前版本, 不执行
    uv run python scripts/init_db.py --sql        # 离线生成 SQL(不连库)

依赖: 真实 PostgreSQL 实例(本机 docker compose up -d postgres).
"""

import argparse
import asyncio
import sys
from pathlib import Path

# 将 src 加入 sys.path, 支持 `python scripts/init_db.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from knowflow.core.config import get_settings  # noqa: E402
from knowflow.core.logging import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)


def _alembic_config() -> Config:
    """构造 Alembic Config, 指向项目内 migrations 目录."""
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SRC / "knowflow" / "db" / "migrations"))
    cfg.set_main_option("prepend_sys_path", str(SRC))
    return cfg


async def _ensure_database() -> None:
    """连接 postgres 库, 若目标库不存在则创建.

    仅在 dev/test 环境下使用; prod 由 DBA 预先创建.
    """
    settings = get_settings()
    if settings.is_prod:
        logger.info("init_db.skip_create_db_in_prod", db=settings.postgres_db)
        return

    # 连接默认 postgres 库执行 CREATE DATABASE
    admin_dsn = (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
    )
    engine = create_async_engine(admin_dsn, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": settings.postgres_db},
            )
            if result.scalar() == 1:
                logger.info("init_db.database_exists", db=settings.postgres_db)
                return
            await conn.execute(text(f'CREATE DATABASE "{settings.postgres_db}"'))
            logger.info("init_db.database_created", db=settings.postgres_db)
    finally:
        await engine.dispose()


def _upgrade_head() -> None:
    """应用 alembic 迁移到 head."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    logger.info("init_db.upgrade_head_done")


def _current_revision() -> None:
    """打印当前 alembic 版本."""
    cfg = _alembic_config()
    command.current(cfg)


def _offline_sql() -> None:
    """离线生成 upgrade SQL(不连接数据库)."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head", sql=True)


async def _run(args: argparse.Namespace) -> int:
    setup_logging()
    settings = get_settings()
    logger.info(
        "init_db.start",
        env=settings.env,
        dsn=settings.postgres_dsn,
        check=args.check,
        sql=args.sql,
    )

    if args.sql:
        # 离线模式: 仅打印 SQL, 不需要数据库
        _offline_sql()
        return 0

    if args.check:
        try:
            await asyncio.to_thread(_current_revision)
        except Exception as exc:
            logger.error("init_db.check_failed", error=str(exc))
            return 1
        return 0

    # 在线模式: 先确保库存在, 再 upgrade
    try:
        await _ensure_database()
    except Exception as exc:
        logger.warning(
            "init_db.ensure_database_failed",
            error=str(exc),
            hint="如果 PG 未启动, 请先 docker compose up -d postgres",
        )
        return 1

    try:
        await asyncio.to_thread(_upgrade_head)
    except Exception as exc:
        logger.error("init_db.upgrade_failed", error=str(exc))
        return 1

    logger.info("init_db.success")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KnowFlow 数据库初始化")
    parser.add_argument("--check", action="store_true", help="仅打印当前 alembic 版本, 不执行迁移")
    parser.add_argument(
        "--sql",
        action="store_true",
        help="离线模式: 生成 upgrade SQL 到 stdout, 不连接数据库",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(_run(args)))
