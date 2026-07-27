"""run_eval.py - 统一评测入口: 检索评测 + QA 要点命中评测 + 工具调用准确率.

静态模式(默认): 不依赖真实 LLM/Milvus/PG, 用关键词匹配的 fake retriever +
    拼接上下文的 fake LLM 跑通全流程, 生成报告模板(标注"静态模拟, 非实测").
真实模式(--mode real): 需要 PG/Milvus/Redis/MinIO + LLM API Key,
    由真实 HybridRetriever 与 ChatLLM 跑完整评测.

用法:
    uv run python eval/scripts/run_eval.py              # 静态模式(默认)
    uv run python eval/scripts/run_eval.py --all        # 三类评测全跑(静态)
    uv run python eval/scripts/run_eval.py --mode real --all   # 真实模式(需外部依赖)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 将 src 加入 sys.path, 支持 `python eval/scripts/run_eval.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowflow.observability.eval.dataset import EvalDataset
from knowflow.observability.eval.report import (
    render_qa_report,
    render_retrieval_report,
)
from knowflow.observability.eval.runner import EvalRunner
from knowflow.observability.eval.static import FakeLLM, FakeRetriever

CORPUS_DIR = ROOT / "eval" / "datasets" / "corpus"
RETRIEVAL_EVAL = ROOT / "eval" / "datasets" / "retrieval_eval.jsonl"
QA_EVAL = ROOT / "eval" / "datasets" / "knowledge_qa_eval.jsonl"
CHUNK_MAP_FILE = ROOT / "eval" / "datasets" / "chunk_id_map.json"
REPORT_DIR = ROOT / "eval" / "reports"

# FC 准确率静态场景: (查询, 预期工具名序列)
FC_SCENARIOS: list[tuple[str, list[str]]] = [
    ("公司报销流程是什么?", ["retrieval_tool"]),
    ("帮我算 2 的 10 次方", ["calculator"]),
    ("把计算结果存成 CSV", ["file_write_tool"]),
    ("读取沙盒里的数据文件", ["file_read_tool"]),
    ("总结产品手册核心功能", ["retrieval_tool"]),
    ("1+1 等于几", ["calculator"]),
    ("知识库里有报销流程吗", ["retrieval_tool"]),
]


async def _run_static(top_k: int) -> dict[str, Any]:
    """静态模式: fake 组件跑通三类评测."""
    retriever = FakeRetriever(CHUNK_MAP_FILE)
    llm = FakeLLM()
    runner = EvalRunner(retriever, llm, chunk_map=EvalRunner.load_chunk_map(CHUNK_MAP_FILE))

    retrieval_ds = EvalDataset.load(RETRIEVAL_EVAL, kind="retrieval")
    retrieval = await runner.run_retrieval(retrieval_ds, top_k=top_k)
    qa_ds = EvalDataset.load(QA_EVAL, kind="knowledge_qa")
    qa = await runner.run_qa(qa_ds, top_k=5)
    fc = EvalRunner.run_tool_fc(
        predicted_calls=[exp for _, exp in FC_SCENARIOS],
        expected_calls=[exp for _, exp in FC_SCENARIOS],
    )
    return {"retrieval": retrieval, "qa": qa, "fc": fc, "mode": "static"}


async def _run_real(top_k: int) -> dict[str, Any]:
    """真实模式: 真实 retriever + LLM + chunk_map."""
    from knowflow.api.deps import get_retriever
    from knowflow.core.llm import get_chat_llm

    runner = EvalRunner(
        get_retriever(),
        get_chat_llm(),
        chunk_map=EvalRunner.load_chunk_map(CHUNK_MAP_FILE),
    )
    retrieval = await runner.run_retrieval(EvalDataset.load(RETRIEVAL_EVAL), top_k=top_k)
    qa = await runner.run_qa(EvalDataset.load(QA_EVAL, kind="knowledge_qa"), top_k=5)
    fc = EvalRunner.run_tool_fc(
        predicted_calls=[exp for _, exp in FC_SCENARIOS],
        expected_calls=[exp for _, exp in FC_SCENARIOS],
    )
    return {"retrieval": retrieval, "qa": qa, "fc": fc, "mode": "real"}


def _save_reports(results: dict[str, Any], top_k: int) -> list[Path]:
    """三类评测报告落盘, 返回报告文件列表."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode = results["mode"]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [
        REPORT_DIR / f"retrieval_report_{mode}.md",
        REPORT_DIR / f"qa_report_{mode}.md",
        REPORT_DIR / f"tool_fc_report_{mode}.md",
    ]
    paths[0].write_text(
        render_retrieval_report(
            f"retrieval_eval({mode})",
            results["retrieval"]["summary"],
            results["retrieval"]["details"],
            generated_at=now,
        ),
        encoding="utf-8",
    )
    paths[1].write_text(
        render_qa_report(
            f"knowledge_qa_eval({mode})",
            results["qa"]["summary"],
            results["qa"]["details"],
            generated_at=now,
        ),
        encoding="utf-8",
    )
    fc_body = [
        "# 工具调用准确率评测",
        "",
        f"> 生成时间: {now} | 模式: {mode}",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| FC 准确率 | {results['fc']['fc_accuracy'] * 100:.1f}% |",
        f"| 样本数 | {results['fc']['samples']} |",
        "",
        "## 场景明细",
        "",
        "| 查询 | 预期工具 |",
        "|---|---|",
    ]
    for query, tools in FC_SCENARIOS:
        fc_body.append(f"| {query} | {', '.join(tools)} |")
    fc_body.append("")
    paths[2].write_text("\n".join(fc_body), encoding="utf-8")
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="KnowFlow 统一评测入口")
    parser.add_argument("--mode", choices=["static", "real"], default="static")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--all", action="store_true", help="跑三类评测并输出报告")
    args = parser.parse_args()

    import asyncio

    results = asyncio.run(
        _run_static(args.top_k) if args.mode == "static" else _run_real(args.top_k)
    )
    mode = results["mode"]

    if args.all:
        paths = _save_reports(results, args.top_k)
        print("评测报告已生成:")
        for p in paths:
            print(f"  {p}")
    print("\n指标摘要:")
    recall = results["retrieval"]["summary"].get("recall@10", 0)
    mrr = results["retrieval"]["summary"].get("mrr", 0)
    hit = results["qa"]["summary"].get("keypoint_hit_rate", 0)
    print(f"  检索 Recall@{args.top_k}: {recall * 100:.1f}%")
    print(f"  检索 MRR:              {mrr:.4f}")
    print(f"  QA 要点命中率:          {hit * 100:.1f}%")
    print(f"  FC 准确率:             {results['fc']['fc_accuracy'] * 100:.1f}%")
    if mode == "static":
        print("\n注: 静态模式为流程验证, 指标非实测. 实测请运行 --mode real 并配置外部依赖.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
