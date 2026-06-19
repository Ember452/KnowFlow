"""工具指标统计单测 - 调用记录与治理级快照.

call_stats(): 总调用数/成功率/平均 token/平均耗时.
governance_stats(): 可见工具数均值/Schema Token 均值/FC 准确率.
"""

from knowflow.tools.metrics import ToolMetrics

# ── call_stats ──


def test_call_stats_empty() -> None:
    """无调用记录时返回零值."""
    stats = ToolMetrics().call_stats()
    assert stats["total_calls"] == 0
    assert stats["success_rate"] == 0.0


def test_call_stats_records() -> None:
    """记录调用后统计正确."""
    m = ToolMetrics()
    m.record_call("calc", True, tokens=10, latency_ms=5.0)
    m.record_call("calc", False, tokens=0, latency_ms=3.0)
    stats = m.call_stats()
    assert stats["total_calls"] == 2
    assert stats["success_rate"] == 0.5
    assert stats["avg_tokens"] == 5.0  # (10+0)/2
    assert stats["avg_latency_ms"] == 4.0  # (5+3)/2


def test_call_stats_all_success() -> None:
    """全部成功时成功率 1.0."""
    m = ToolMetrics()
    m.record_call("a", True)
    m.record_call("b", True)
    assert m.call_stats()["success_rate"] == 1.0


# ── governance_stats ──


def test_governance_stats_empty() -> None:
    """无快照时返回零值."""
    stats = ToolMetrics().governance_stats()
    assert stats["avg_visible_count"] == 0.0
    assert stats["avg_schema_tokens"] == 0.0
    assert stats["fc_accuracy"] == 0.0
    assert stats["scenarios"] == 0


def test_governance_stats_snapshots() -> None:
    """记录快照后统计均值与准确率."""
    m = ToolMetrics()
    m.snapshot(visible_count=6, schema_tokens=200, fc_correct=True, scenario="baseline")
    m.snapshot(visible_count=4, schema_tokens=140, fc_correct=True, scenario="isolated")
    m.snapshot(visible_count=4, schema_tokens=140, fc_correct=False, scenario="miss")
    stats = m.governance_stats()
    assert stats["scenarios"] == 3
    assert stats["avg_visible_count"] == round((6 + 4 + 4) / 3, 2)  # 4.67
    assert stats["avg_schema_tokens"] == round((200 + 140 + 140) / 3, 2)  # 160.0
    assert stats["fc_accuracy"] == round(2 / 3, 4)  # 0.6667


def test_snapshot_records_scenario_name() -> None:
    """快照记录 scenario 标签."""
    m = ToolMetrics()
    m.snapshot(visible_count=1, schema_tokens=10, fc_correct=True, scenario="test_case")
    assert m.snapshots[0].scenario == "test_case"
