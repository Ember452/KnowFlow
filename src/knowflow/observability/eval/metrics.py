"""评测指标计算 - Recall@K / MRR / NDCG@K / 要点命中率 / 工具调用准确率.

全部为纯函数, 不依赖外部服务, 可直接单测.
ranked_ids 为检索返回的相关 id 序列(按相关性降序), relevant_ids 为标注的相关 id 集合.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def recall_at_k(ranked_ids: Sequence[object], relevant_ids: Iterable[object], k: int) -> float:
    """Recall@K: 前 K 个结果中命中相关项的比例(分母为相关项总数)."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    hit = sum(1 for rid in ranked_ids[:k] if rid in relevant)
    return hit / len(relevant)


def mrr(ranked_ids: Sequence[object], relevant_ids: Iterable[object]) -> float:
    """MRR: 首个相关结果的倒数排名, 无命中返回 0."""
    relevant = set(relevant_ids)
    for idx, rid in enumerate(ranked_ids, 1):
        if rid in relevant:
            return 1.0 / idx
    return 0.0


def _dcg(ranked_ids: Sequence[object], relevant_ids: set[object], k: int) -> float:
    """DCG@K: 位置增益 log2(1+rank) 衰减."""
    return sum(
        1.0 / math.log2(idx + 1) for idx, rid in enumerate(ranked_ids[:k], 1) if rid in relevant_ids
    )


def ndcg_at_k(ranked_ids: Sequence[object], relevant_ids: Iterable[object], k: int) -> float:
    """NDCG@K: DCG 按理想排序归一化, 无相关项返回 0."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    dcg = _dcg(ranked_ids, relevant, k)
    # 理想排序: 相关项全部位于最前(取 min(k, |relevant|) 个)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(relevant)) + 1))
    return dcg / ideal if ideal > 0 else 0.0


def keypoint_hit_rate(answer: str, keypoints: Iterable[str]) -> float:
    """要点命中率: 答案包含全部要点的比例(子串匹配, 忽略空白差异)."""
    normalized = " ".join(answer.split())
    kps = [kp for kp in keypoints if kp.strip()]
    if not kps:
        return 0.0
    hits = sum(1 for kp in kps if " ".join(kp.split()) in normalized)
    return hits / len(kps)


def fc_accuracy(
    predicted_calls: Sequence[Sequence[str]],
    expected_calls: Sequence[Sequence[str]],
) -> float:
    """工具调用准确率: 每次调用的工具名序列与期望完全一致的比例.

    工具名序列按调用顺序比较(顺序敏感, 与工具编排语义一致);
    仅统计期望非空且实际发生了调用的条目(避免"不调用即满分").
    """
    if not expected_calls:
        return 0.0
    scored = [(pred, exp) for pred, exp in zip(predicted_calls, expected_calls, strict=True) if exp]
    if not scored:
        return 0.0
    correct = sum(1 for pred, exp in scored if list(pred) == list(exp))
    return correct / len(scored)


def average(values: Sequence[float]) -> float:
    """序列均值, 空序列返回 0."""
    return sum(values) / len(values) if values else 0.0


def summarize_retrieval(results: Sequence[dict]) -> dict[str, float]:
    """检索评测汇总: 各 top_k 的 Recall/MRR/NDCG 均值."""
    if not results:
        return {}
    summary: dict[str, float] = {"mrr": average([float(r["mrr"]) for r in results])}
    for key in ("recall@5", "recall@10", "ndcg@10"):
        values = [float(r[key]) for r in results if key in r]
        if values:
            summary[key] = average(values)
    return summary
