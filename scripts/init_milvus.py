"""Milvus collection 初始化脚本.

职责:
1. 创建 settings.milvus_collection(若不存在)
2. 创建 HNSW 索引(IP 度量, M=16, efConstruction=200)
3. --reset: 先删除再重建

用法:
    uv run python scripts/init_milvus.py           # 创建 collection(若不存在)
    uv run python scripts/init_milvus.py --reset    # 删除重建 collection
    uv run python scripts/init_milvus.py --help     # 查看帮助

依赖: 真实 Milvus 实例(本机 docker compose up -d milvus).

Collection schema:
    id (INT64, primary key) = chunk_id
    doc_id (INT64)
    embedding (FLOAT_VECTOR, dim=1024)
    索引: HNSW (M=16, efConstruction=200), 度量 IP
"""

import argparse
import sys
from pathlib import Path

# 将 src 加入 sys.path, 支持 `python scripts/init_milvus.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pymilvus import DataType, MilvusClient  # noqa: E402

from knowflow.core.config import get_settings  # noqa: E402
from knowflow.core.logging import get_logger, setup_logging  # noqa: E402

logger = get_logger(__name__)


def create_collection(client: MilvusClient, collection_name: str, dim: int) -> None:
    """创建 collection + HNSW 索引.

    Args:
        client: MilvusClient 实例.
        collection_name: collection 名.
        dim: 向量维度.
    """
    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("doc_id", DataType.INT64)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="IP",
        params={"M": 16, "efConstruction": 200},
    )

    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )
    logger.info(
        "init_milvus.collection_created",
        collection=collection_name,
        dim=dim,
        index="HNSW",
        metric="IP",
    )


def run(args: argparse.Namespace) -> int:
    """执行初始化.

    Returns:
        0 成功, 1 失败.
    """
    setup_logging()
    settings = get_settings()
    collection_name = settings.milvus_collection
    dim = settings.milvus_dim

    logger.info(
        "init_milvus.start",
        uri=settings.milvus_uri,
        collection=collection_name,
        dim=dim,
        reset=args.reset,
    )

    try:
        client = MilvusClient(uri=settings.milvus_uri)
    except Exception as exc:
        logger.error(
            "init_milvus.connect_failed",
            error=str(exc),
            hint="如果 Milvus 未启动, 请先 docker compose up -d milvus",
        )
        return 1

    try:
        if client.has_collection(collection_name):
            if args.reset:
                client.drop_collection(collection_name)
                logger.info("init_milvus.collection_dropped", collection=collection_name)
            else:
                logger.info("init_milvus.collection_exists", collection=collection_name)
                return 0

        create_collection(client, collection_name, dim)

        # 验证创建成功
        if not client.has_collection(collection_name):
            logger.error("init_milvus.verify_failed", collection=collection_name)
            return 1

        logger.info("init_milvus.success", collection=collection_name)
        return 0
    except Exception as exc:
        logger.error("init_milvus.failed", error=str(exc))
        return 1
    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KnowFlow Milvus collection 初始化")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="删除重建 collection(清空全部向量数据)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run(args))
