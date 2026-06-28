"""评测报告渲染单测 - Markdown 输出结构与数值格式."""

from knowflow.observability.eval.report import (
    render_final_report,
    render_qa_report,
    render_retrieval_report,
)


def test_render_retrieval_report() -> None:
    """检索报告: 总览表 + 明细表 + 百分比格式."""
    report = render_retrieval_report(
        "retrieval_eval(static)",
        {"recall@5": 0.23, "recall@10": 0.3, "mrr": 0.2183, "ndcg@10": 0.25},
        [{"query": "年假", "recall@10": 1.0, "mrr": 1.0, "ndcg@10": 1.0}],
        generated_at="2026-08-07",
    )
    assert "# 检索评测报告" in report
    assert "| recall@10 | 30.00% |" in report
    assert "| 年假" in report
    assert "生成时间: 2026-08-07" in report


def test_render_qa_report() -> None:
    """QA 报告: 要点命中率总览."""
    report = render_qa_report(
        "knowledge_qa_eval(static)",
        {"keypoint_hit_rate": 0.172},
        [{"query": "报销", "keypoint_hit_rate": 0.5, "keypoint_count": 2}],
        generated_at="2026-08-07",
    )
    assert "# QA 评测报告" in report
    assert "| 要点命中率(均值) | 17.20% |" in report
    assert "| 报销 | 50.00% | 2 |" in report


def test_render_final_report() -> None:
    """总报告: 核心指标表 + 章节正文."""
    report = render_final_report(
        [
            {
                "rows": [
                    {
                        "metric": "可见工具数下降",
                        "value": "-43.4%",
                        "target": "-34.2%",
                        "source": "tool_governance_20260807.md",
                    }
                ],
                "title": "工具治理",
                "body": "执行域隔离说明",
            }
        ],
        generated_at="2026-08-07",
    )
    assert "# KnowFlow 指标总报告" in report
    assert "| 可见工具数下降 | -43.4% | -34.2% |" in report
    assert "## 工具治理" in report
    assert "执行域隔离说明" in report
