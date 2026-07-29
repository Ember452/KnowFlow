"""run_report_eval.py - 报告流水线评测: 引用覆盖率/幻觉率/章节完整率.

指标口径(与设计文档 5.4 一致):
- 引用覆盖率: 报告全部 [n] 中可定位到证据包的比例(1 - 越界比例);
- 幻觉率: 无法定位的引用占比(越界引用数 / 总引用数);
- 章节完整率: 达到最短长度要求的章节占比.

静态模式(默认): fake retriever + 报告专用 fake LLM 跑通流水线, 输出指标
(标注"静态模拟, 非实测"). 真实模式(--mode real): 真实 LLM/检索器/记忆源跑完整评测.

用法:
    uv run python eval/scripts/run_report_eval.py              # 静态模式(默认)
    uv run python eval/scripts/run_report_eval.py --mode real  # 真实模式(需外部依赖)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# 将 src 加入 sys.path, 支持 `python eval/scripts/run_report_eval.py` 直接执行
ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from knowflow.agents.report.pipeline import ReportPipeline
from knowflow.agents.report.reviewer import extract_citations
from knowflow.observability.eval.static import FakeLLM, FakeRetriever

REPORT_EVAL = ROOT / "eval" / "datasets" / "report_eval.jsonl"
CHUNK_MAP_FILE = ROOT / "eval" / "datasets" / "chunk_id_map.json"
REPORT_DIR = ROOT / "eval" / "reports"

_MIN_BODY_CHARS = 30  # 与 reviewer._MIN_BODY_CHARS 保持一致


class ReportFakeLLM(FakeLLM):
    """报告评测静态 LLM: 规划回合法大纲, 撰写回带 [n] 引用的模板正文.

    引用下标取自用户消息中证据素材的实际下标(模拟真实引用行为),
    无证据时回 [1](越界, 如实反映低覆盖率).
    """

    async def ainvoke(self, messages: Any) -> str:
        system = next(m["content"] for m in messages if m["role"] == "system")
        if "研究报告规划师" in system:
            return (
                '{"title": "制度要点总结", '
                '"chapters": [{"title": "核心规则", "queries": ["报销流程"]}, '
                '{"title": "执行细节", "queries": ["审批权限"]}]}'
            )
        if "报告撰写专家" in system:
            user = next(m["content"] for m in messages if m["role"] == "user")
            indexes = re.findall(r"\[(\d+)\]", user)
            cites = " ".join(f"[{i}]" for i in indexes[:3]) or "[1]"
            return f"该主题现状清晰, 关键规则见 {cites}, 需结合知识库证据进一步确认。"
        if "报告审查员" in system:
            return '{"passed": true, "issues": []}'
        return await super().ainvoke(messages)


def load_dataset(path: Path) -> list[dict[str, Any]]:
    """加载报告评测集(jsonl)."""
    items: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            items.append(json.loads(line))
    return items


def compute_metrics(result: Any) -> dict[str, float]:
    """按口径计算引用覆盖率/幻觉率/章节完整率."""
    total = 0
    invalid = 0
    short = 0
    for ch in result.chapters:
        cites = extract_citations(ch.body)
        total += len(cites)
        invalid += sum(1 for n in cites if n < 1 or n > len(result.evidence))
        if len(ch.body.strip()) < _MIN_BODY_CHARS:
            short += 1
    return {
        "citation_coverage": (total - invalid) / total if total else 0.0,
        "hallucination_rate": invalid / total if total else 0.0,
        "chapter_completeness": (len(result.chapters) - short) / len(result.chapters)
        if result.chapters
        else 0.0,
    }


async def _run_static() -> list[dict[str, Any]]:
    """静态模式: fake 组件跑通流水线并输出指标."""
    retriever = FakeRetriever(CHUNK_MAP_FILE)
    pipeline = ReportPipeline(llm=ReportFakeLLM(), retriever=retriever)
    cases: list[dict[str, Any]] = []
    for item in load_dataset(REPORT_EVAL):
        result = await pipeline.run(item["query"])
        cases.append(
            {
                "query": item["query"],
                "sections": len(result.chapters),
                "evidence": len(result.evidence),
                "review_passed": bool(result.review and result.review.passed),
                "metrics": compute_metrics(result),
                "mode": "static",
            }
        )
    return cases


async def _run_real() -> list[dict[str, Any]]:
    """真实模式: 真实 LLM/检索器/记忆源跑完整流水线."""
    from knowflow.api.deps import get_report_service

    service = get_report_service()
    if service is None or service.pipeline is None:
        raise RuntimeError("报告服务不可用(依赖未就绪)")
    pipeline = service.pipeline
    cases: list[dict[str, Any]] = []
    for item in load_dataset(REPORT_EVAL):
        result = await pipeline.run(item["query"])
        cases.append(
            {
                "query": item["query"],
                "sections": len(result.chapters),
                "evidence": len(result.evidence),
                "review_passed": bool(result.review and result.review.passed),
                "metrics": compute_metrics(result),
                "mode": "real",
            }
        )
    return cases


def _render_report(cases: list[dict[str, Any]], mode: str) -> Path:
    """渲染评测报告 Markdown 到 eval/reports/."""
    now = datetime.now().strftime("%Y%m%d")
    name = f"report_eval_{now}.md"
    path = REPORT_DIR / name
    agg = {
        k: sum(c["metrics"][k] for c in cases) / len(cases)
        for k in ("citation_coverage", "hallucination_rate", "chapter_completeness")
    }
    mode_desc = "静态模拟, 非实测" if mode == "static" else "真实环境实测"
    lines = [
        "# 报告流水线评测报告",
        "",
        f"> 日期: {now}  模式: {mode}({mode_desc})",
        "",
        "## 指标总览",
        "",
        "| 指标 | 均值 |",
        "|---|---|",
        f"| 引用覆盖率 | {agg['citation_coverage']:.1%} |",
        f"| 幻觉率 | {agg['hallucination_rate']:.1%} |",
        f"| 章节完整率 | {agg['chapter_completeness']:.1%} |",
        "",
        "## 用例明细",
        "",
        "| 查询 | 章节数 | 证据数 | 核查通过 | 引用覆盖率 | 幻觉率 | 章节完整率 |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cases:
        m = c["metrics"]
        lines.append(
            f"| {c['query']} | {c['sections']} | {c['evidence']} | "
            f"{c['review_passed']} | {m['citation_coverage']:.1%} | "
            f"{m['hallucination_rate']:.1%} | {m['chapter_completeness']:.1%} |"
        )
    lines += [
        "",
        "> 口径: 引用覆盖率=可定位引用/总引用; 幻觉率=越界引用/总引用; 章节完整率=达标章节/总章节.",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main() -> None:
    parser = argparse.ArgumentParser(description="报告流水线评测")
    parser.add_argument("--mode", choices=["static", "real"], default="static")
    args = parser.parse_args()

    cases = await _run_real() if args.mode == "real" else await _run_static()
    path = _render_report(cases, args.mode)
    print(f"报告评测完成: {path}")
    print(f"用例数: {len(cases)}")
    for k in ("citation_coverage", "hallucination_rate", "chapter_completeness"):
        mean = sum(c["metrics"][k] for c in cases) / len(cases)
        print(f"  {k}: {mean:.1%}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
