"""生成 OpenAPI 文档 - 从 FastAPI app 导出 openapi.json.

用法: uv run python scripts/gen_openapi.py [--out openapi.json]
验收: P4 要求 `uv run python scripts/gen_openapi.py` 成功生成.
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 KnowFlow OpenAPI 文档")
    parser.add_argument("--out", default="openapi.json", help="输出文件路径")
    args = parser.parse_args()

    # 将 src/ 加入 sys.path, 便于直接运行
    src = Path(__file__).resolve().parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from knowflow.main import create_app

    app = create_app()
    spec = app.openapi()
    out_path = Path(args.out)
    out_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI 文档已生成: {out_path} ({out_path.stat().st_size} bytes)")
    print(f"  路径数: {len(spec.get('paths', {}))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
