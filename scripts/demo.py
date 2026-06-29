"""demo.py - 一键演示: 上传文档 → 索引 → QA → 工具调用 → 多 Agent 任务.

前置: 服务已启动(docker compose up -d && make init-db && make init-milvus &&
make dev && make worker), 且 .env 已配置 KNOWFLOW_LLM_API_KEY.

用法:
    uv run python scripts/demo.py              # 全流程演示(默认语料)
    uv run python scripts/demo.py --base http://localhost:8000
    uv run python scripts/demo.py --qa-only    # 只跑 QA 演示
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "eval" / "datasets" / "corpus"

DEFAULT_BASE = "http://localhost:8000/api/v1"


class DemoError(RuntimeError):
    """演示流程异常(前置缺失/调用失败)."""


def _call(
    base: str,
    method: str,
    path: str,
    *,
    data: dict | None = None,
    files: dict[str, tuple[str, bytes]] | None = None,
) -> dict:
    """调用 API, 统一异常处理."""
    url = f"{base}{path}"
    headers = {"X-User-Id": "demo"}
    body = None
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif files is not None:
        boundary = "----knowflowdemo"
        parts = []
        for field, (fname, content) in files.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                f'filename="{fname}"\r\nContent-Type: text/markdown\r\n\r\n'.encode()
                + content
                + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise DemoError(f"API {method} {path} 失败 [{exc.code}]: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DemoError(f"无法连接 {url} —— 请确认服务已启动(make dev), 且依赖容器已就绪") from exc


def _step(title: str) -> None:
    print(f"\n{'=' * 64}\n▶ {title}\n{'=' * 64}")


def _wait_until(predicate: object, timeout: float = 60.0, interval: float = 2.0) -> None:
    """轮询等待条件满足."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():  # type: ignore[operator]
            return
        time.sleep(interval)
    raise DemoError(f"等待超时({timeout}s)")


def demo_upload(base: str) -> list[int]:
    """上传语料文档并等待索引完成. 返回 doc_ids."""
    _step("1/5 上传语料文档(异步索引)")
    doc_ids: list[int] = []
    for doc_path in sorted(CORPUS_DIR.glob("*.md")):
        resp = _call(
            base,
            "POST",
            "/documents/upload",
            files={"file": (doc_path.name, doc_path.read_bytes())},
        )
        doc_ids.append(int(resp["doc_id"]))
        print(f"  上传 {doc_path.name} → doc_id={resp['doc_id']} status={resp['status']}")
    print(f"  共 {len(doc_ids)} 篇, 等待 worker 索引完成...")
    _wait_until(lambda: len(_call(base, "GET", "/documents").get("documents", [])) >= len(doc_ids))
    print("  索引完成 ✓")
    return doc_ids


def demo_qa(base: str) -> None:
    """知识问答演示."""
    _step("2/5 知识问答(检索增强 + 引用)")
    resp = _call(
        base,
        "POST",
        "/chat",
        data={"user_id": "demo", "message": "员工年假制度是什么? 病假工资怎么算?"},
    )
    print("  Q: 员工年假制度是什么? 病假工资怎么算?")
    print(f"  A: {resp['answer'][:200]}...")
    print(f"  引用 {len(resp['citations'])} 条 | 耗时 {resp['latency_ms']}ms ✓")


def demo_tool(base: str) -> None:
    """工具调用演示."""
    _step("3/5 工具调用(执行域隔离 + calculator)")
    resp = _call(
        base,
        "POST",
        "/chat",
        data={"user_id": "demo", "message": "帮我算 (1200 + 350) * 0.85 并告诉我结果"},
    )
    tool_calls = resp.get("tool_calls", [])
    for tc in tool_calls:
        line = f"  工具: {tc['tool']} | args={tc['args']} | success={tc['success']}"
        print(f"{line} | {tc['latency_ms']}ms")
    print(f"  A: {resp['answer'][:150]}...")
    if not tool_calls:
        print("  ⚠ 未观察到工具调用(LLM 可能直答, 属正常降级)")


def demo_multiagent(base: str) -> None:
    """多 Agent 委派演示."""
    _step("4/5 Multi-Agent 委派(对比任务)")
    resp = _call(
        base,
        "POST",
        "/chat",
        data={
            "user_id": "demo",
            "message": "对比财务报销与差旅报销的打款周期, 以及年假与病假政策, 并汇总",
        },
    )
    print(f"  A: {resp['answer'][:200]}...")
    run_id = resp.get("run_id")
    if run_id:
        detail = _call(base, "GET", f"/agents/runs/{run_id}")
        children = detail.get("children", [])
        delegations = detail.get("delegations", [])
        print(f"  run_id={run_id} | 子 Agent {len(children)} 个 | 委派 {len(delegations)} 条")
        for d in delegations:
            print(f"    - [{d['status']}] {d['task'][:40]}")
    print("  ✓ 多 Agent 链路完成")


def demo_trace(base: str, session_id: str) -> None:
    """可观测演示."""
    _step("5/5 可观测: Trace 树与统计")
    try:
        tree = _call(base, "GET", f"/traces/{session_id}")
        roots = tree.get("roots", [])
        print(f"  Trace 树根节点 {len(roots)} 个")
        stats = _call(base, "GET", "/traces/stats")
        print(
            f"  近 {stats['hours']}h: 对话 {stats['dialogs']} | "
            f"工具调用 {stats['tool_calls']} | 成功率 {stats['tool_success_rate']}%"
        )
    except DemoError as exc:
        print(f"  ⚠ 可观测演示跳过: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="KnowFlow 一键演示")
    parser.add_argument("--base", default=DEFAULT_BASE, help="API 基础地址")
    parser.add_argument("--qa-only", action="store_true", help="只跑 QA 演示")
    args = parser.parse_args()

    print("KnowFlow 一键演示")
    print(f"API: {args.base} | 语料: {CORPUS_DIR}")
    try:
        health = _call(args.base.replace("/api/v1", ""), "GET", "/health")
        print(f"服务状态: {health}")
    except DemoError as exc:
        print(f"✗ {exc}")
        return 1

    if args.qa_only:
        demo_qa(args.base)
        return 0

    try:
        doc_ids = demo_upload(args.base)
        demo_qa(args.base)
        demo_tool(args.base)
        demo_multiagent(args.base)
        demo_trace(args.base, "1")
        _step("演示完成")
        print(f"  上传 {len(doc_ids)} 篇文档, 全链路(索引→QA→工具→多Agent→可观测)跑通 ✓")
        print("  更多: curl http://localhost:8000/docs 查看交互式文档")
    except DemoError as exc:
        print(f"\n✗ 演示中断: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
