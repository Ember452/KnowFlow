"""依赖连通性检查脚本.

逐个探测 PostgreSQL / Redis / Milvus / MinIO 是否可用, 输出对勾或叉.
用法: uv run python scripts/check_env.py
"""

import asyncio
import sys

# 确保从项目根目录运行时能导入 knowflow
from knowflow.core.config import get_settings
from knowflow.core.logging import setup_logging


async def check_postgres() -> tuple[bool, str]:
    try:
        from knowflow.db.base import dispose_engine, init_engine

        await init_engine()
        await dispose_engine()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def check_redis() -> tuple[bool, str]:
    try:
        from knowflow.db.redis import dispose_redis, init_redis

        await init_redis()
        await dispose_redis()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_milvus() -> tuple[bool, str]:
    try:
        from knowflow.db.milvus import dispose_milvus, init_milvus

        init_milvus()
        dispose_milvus()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def check_minio() -> tuple[bool, str]:
    try:
        from knowflow.db.minio import dispose_minio, init_minio

        init_minio()
        dispose_minio()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


async def main() -> int:
    setup_logging()
    settings = get_settings()
    print(f"\nKnowFlow 依赖连通性检查 (env={settings.env})\n")

    pg_ok, pg_msg = await check_postgres()
    rd_ok, rd_msg = await check_redis()
    mv_ok, mv_msg = check_milvus()
    mn_ok, mn_msg = check_minio()

    checks = [
        ("PostgreSQL", settings.postgres_dsn, pg_ok, pg_msg),
        ("Redis", settings.redis_url, rd_ok, rd_msg),
        ("Milvus", settings.milvus_uri, mv_ok, mv_msg),
        ("MinIO", settings.minio_endpoint, mn_ok, mn_msg),
    ]

    for name, addr, ok, msg in checks:
        mark = "[OK]" if ok else "[FAIL]"
        line = f"  {mark}  {name:<10} {addr}"
        if not ok:
            line += f"  -> {msg}"
        print(line)

    all_ok = all(ok for _, _, ok, _ in checks)
    print()
    print("全部就绪" if all_ok else "部分依赖不可用, 请先 docker compose up -d")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
