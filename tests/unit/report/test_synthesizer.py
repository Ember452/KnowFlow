"""证据融合器单测 - 章节聚合/近似去重/空输入."""

from knowflow.agents.report.models import Evidence, EvidenceSource
from knowflow.agents.report.synthesizer import Synthesizer


def _ev(content: str) -> Evidence:
    return Evidence(source=EvidenceSource.KNOWLEDGE, content=content)


def test_synthesize_aggregates_and_indexes() -> None:
    """多章节证据聚合为全局包, 章节→下标映射 1-based 保序."""
    pack = Synthesizer().synthesize(
        {
            "一": [_ev("A"), _ev("B")],
            "二": [_ev("C")],
        }
    )
    assert len(pack.evidence) == 3
    assert pack.chapter_index["一"] == [1, 2]
    assert pack.chapter_index["二"] == [3]
    assert [e.content for e in pack.evidence] == ["A", "B", "C"]


def test_synthesize_dedup_skips_near_duplicate() -> None:
    """内容近似相似(ratio >= 0.9)的证据被去重, 保留先到者."""
    pack = Synthesizer().synthesize(
        {
            "一": [_ev("报销需要提交申请单并审批"), _ev("报销需要提交申请单并审批。")],
        }
    )
    assert len(pack.evidence) == 1
    assert pack.chapter_index["一"] == [1]


def test_synthesize_different_content_kept() -> None:
    """内容差异大的证据不误去重."""
    pack = Synthesizer().synthesize(
        {
            "一": [_ev("报销流程说明"), _ev("年假申请规则")],
        }
    )
    assert len(pack.evidence) == 2


def test_synthesize_empty_input() -> None:
    """空输入返回空包."""
    pack = Synthesizer().synthesize({})
    assert pack.evidence == []
    assert pack.chapter_index == {}


def test_synthesize_skips_blank_content() -> None:
    """空白内容证据被过滤."""
    pack = Synthesizer().synthesize({"一": [_ev(""), _ev("有效内容")]})
    assert len(pack.evidence) == 1
