"""评测报告生成 - Markdown 报告渲染.

run_eval.py 产出结构化结果 dict, 本模块渲染为可读报告:
总览表 + 分任务集明细 + 结论. 同时汇总 compare_baseline / benchmark 脚本结果.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_retrieval_report(
    name: str,
    summary: dict[str, float],
    detail_rows: list[dict[str, Any]],
    *,
    generated_at: str = "",
) -> str:
    """渲染检索评测报告(单数据集)."""
    lines = [
        f"# 检索评测报告: {name}",
        "",
        f"> 生成时间: {generated_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 样本数: {len(detail_rows)}",
        "",
        "## 指标总览",
        "",
        "| 指标 | 值 |",
        "|---|---|",
    ]
    for key in sorted(summary):
        lines.append(f"| {key} | {_pct(summary[key])} |")
    lines += [
        "",
        "## 明细(前 10 条)",
        "",
        "| query | Recall@10 | MRR | NDCG@10 |",
        "|---|---|---|---|",
    ]
    for row in detail_rows[:10]:
        lines.append(
            f"| {row['query'][:40]} | {_pct(row['recall@10'])} | "
            f"{_pct(row['mrr'])} | {_pct(row['ndcg@10'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_qa_report(
    name: str,
    summary: dict[str, float],
    detail_rows: list[dict[str, Any]],
    *,
    generated_at: str = "",
) -> str:
    """渲染 QA 评测报告(要点命中率)."""
    lines = [
        f"# QA 评测报告: {name}",
        "",
        f"> 生成时间: {generated_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 样本数: {len(detail_rows)}",
        "",
        "## 指标总览",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 要点命中率(均值) | {_pct(summary.get('keypoint_hit_rate', 0.0))} |",
        "",
        "## 明细(前 10 条)",
        "",
        "| query | 要点命中 | 要点数 |",
        "|---|---|---|",
    ]
    for row in detail_rows[:10]:
        lines.append(
            f"| {row['query'][:40]} | {_pct(row['keypoint_hit_rate'])} | {row['keypoint_count']} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_final_report(sections: list[dict[str, Any]], *, generated_at: str = "") -> str:
    """渲染总报告: 五个核心指标 + 各模块报告摘要."""
    lines = [
        "# KnowFlow 指标总报告(final_report)",
        "",
        f"> 生成时间: {generated_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 核心指标总览",
        "",
        "| 指标 | 实测 | 目标 | 数据来源 |",
        "|---|---|---|---|",
    ]
    for sec in sections:
        for row in sec.get("rows", []):
            lines.append(
                f"| {row['metric']} | {row['value']} | {row['target']} | {row['source']} |"
            )
    for sec in sections:
        title = sec.get("title", "")
        if not title:
            continue
        lines += ["", f"## {title}", "", sec.get("body", "")]
    lines.append("")
    return "\n".join(lines)
