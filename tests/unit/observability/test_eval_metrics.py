"""评测指标单测 - Recall@K/MRR/NDCG/要点命中/FC 准确率."""

from knowflow.observability.eval.metrics import (
    average,
    fc_accuracy,
    keypoint_hit_rate,
    mrr,
    ndcg_at_k,
    recall_at_k,
)


def test_recall_at_k() -> None:
    """前 K 命中比例, 分母为相关总数."""
    ranked = [10, 20, 30, 40, 50]
    assert recall_at_k(ranked, [10, 50], 2) == 0.5  # 2 个相关中命中 1 个
    assert recall_at_k(ranked, [10], 5) == 1.0
    assert recall_at_k(ranked, [99], 5) == 0.0
    assert recall_at_k(ranked, [], 5) == 0.0  # 无标注返回 0


def test_mrr() -> None:
    """首个相关结果的倒数排名."""
    assert mrr([10, 20, 30], [30]) == 1 / 3
    assert mrr([10, 20, 30], [10]) == 1.0
    assert mrr([10, 20, 30], [99]) == 0.0


def test_ndcg_at_k() -> None:
    """NDCG: 理想排序为 1, 无相关为 0, 位置越前权重越高."""
    assert ndcg_at_k([10, 20], [10, 20], 2) == 1.0  # 全部相关且顺序理想
    assert ndcg_at_k([10, 20], [99], 2) == 0.0
    # 相关在位置 2 vs 位置 1: 前者 NDCG 更低
    later = ndcg_at_k([10, 20], [20], 2)
    first = ndcg_at_k([20, 10], [20], 2)
    assert 0 < later < first <= 1.0


def test_keypoint_hit_rate() -> None:
    """答案包含要点的比例, 忽略空白差异."""
    answer = "报销需填表并提交部门审批"
    assert keypoint_hit_rate(answer, ["提交部门审批", "填表"]) == 1.0
    assert keypoint_hit_rate(answer, ["提交部门审批", "需要 CEO 审批"]) == 0.5
    assert keypoint_hit_rate(answer, []) == 0.0
    # 空白差异不影响命中
    assert keypoint_hit_rate("A  B", ["A B"]) == 1.0


def test_fc_accuracy() -> None:
    """工具调用准确率: 序列完全一致才计为正确."""
    pred = [["retrieval", "calculator"], ["retrieval"]]
    exp = [["retrieval", "calculator"], ["retrieval", "search"]]
    assert fc_accuracy(pred, exp) == 0.5
    # 期望为空(不应调用工具)的条目不计入分母
    assert fc_accuracy([["calculator"]], [[]]) == 0.0
    # 未发生调用的条目不参与评分
    assert fc_accuracy([[]], [["retrieval"]]) == 0.0


def test_average() -> None:
    """空序列返回 0."""
    assert average([1.0, 2.0, 3.0]) == 2.0
    assert average([]) == 0.0
