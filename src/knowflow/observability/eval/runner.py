"""评测执行器 - 检索评测 / QA 要点命中评测 / 工具调用准确率评测.

依赖注入: retriever(实现 async retrieve(query, top_k) -> result.chunks) 与
llm(实现 async ainvoke(messages)) 可注入 fake, 不依赖真实服务.
doc_ids 标注经 chunk_map(doc_id -> [chunk_ids]) 展开为 chunk 级相关.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowflow.core.logging import get_logger
from knowflow.observability.eval.dataset import EvalDataset
from knowflow.observability.eval.metrics import (
    average,
    fc_accuracy,
    keypoint_hit_rate,
    mrr,
    ndcg_at_k,
    recall_at_k,
)

logger = get_logger(__name__)


class EvalRunner:
    """评测执行器: 三类评测的统一入口."""

    def __init__(
        self,
        retriever: Any,
        llm: Any,
        chunk_map: dict[int, list[int]] | None = None,
    ) -> None:
        """初始化.

        Args:
            retriever: HybridRetriever 或 fake(实现 async retrieve).
            llm: langchain BaseChatModel 或 fake(实现 async ainvoke).
            chunk_map: doc_id -> [chunk_ids]; None 时检索评测仅算 doc 级指标.
        """
        self._retriever = retriever
        self._llm = llm
        self._chunk_map = chunk_map or {}

    @classmethod
    def load_chunk_map(cls, path: str | Path) -> dict[int, list[int]]:
        """加载 chunk_id_map.json(doc_id -> [chunk_ids])."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return {int(k): [int(x) for x in v] for k, v in raw.items()}

    # ── 检索评测 ──

    async def run_retrieval(self, dataset: EvalDataset, top_k: int = 10) -> dict[str, Any]:
        """逐条检索并计算 Recall@K/MRR/NDCG@K(文档级相关).

        Returns:
            {"summary": {...}, "details": [每条的指标与命中信息]}
        """
        details: list[dict[str, Any]] = []
        for item in dataset.items:
            result = await self._retriever.retrieve(item.query, top_k=top_k)
            ranked = [c.chunk_id for c in result.chunks]
            relevant_chunks = self._relevant_chunks(item.doc_ids)
            if self._chunk_map:
                # chunk 级: 命中 = 返回 chunk 属于相关文档
                doc_of_chunk = {
                    cid: doc_id for doc_id, cids in self._chunk_map.items() for cid in cids
                }
                # 命中集合: 返回 chunk 所属文档中属于相关标注的部分
                hit_docs = {doc_of_chunk.get(cid) for cid in ranked} & set(item.doc_ids)
                relevant_set: set[Any] = set(item.doc_ids)
                ranked_docs = [doc_of_chunk.get(cid) for cid in ranked]
            else:
                hit_docs = set()
                relevant_set = set(item.doc_ids)
                ranked_docs = list(ranked)
            details.append(
                {
                    "query": item.query,
                    "category": item.category,
                    "recall@5": recall_at_k(ranked_docs, relevant_set, 5),
                    "recall@10": recall_at_k(ranked_docs, relevant_set, 10),
                    "mrr": mrr(ranked_docs, relevant_set),
                    "ndcg@10": ndcg_at_k(ranked_docs, relevant_set, 10),
                    "hit_docs": sorted(hit_docs),
                    "ranked_chunk_count": len(ranked),
                    "relevant_chunks": relevant_chunks,
                }
            )
        summary = {
            "recall@5": average([d["recall@5"] for d in details]),
            "recall@10": average([d["recall@10"] for d in details]),
            "mrr": average([d["mrr"] for d in details]),
            "ndcg@10": average([d["ndcg@10"] for d in details]),
        }
        return {"summary": summary, "details": details}

    def _relevant_chunks(self, doc_ids: list[int]) -> list[int]:
        """相关文档展开为相关 chunk 列表(无映射时为空)."""
        return [cid for doc_id in doc_ids for cid in self._chunk_map.get(doc_id, [])]

    # ── QA 要点命中评测 ──

    async def run_qa(self, dataset: EvalDataset, top_k: int = 5) -> dict[str, Any]:
        """逐条检索 + LLM 生成答案, 计算要点命中率."""
        details: list[dict[str, Any]] = []
        for item in dataset.items:
            result = await self._retriever.retrieve(item.query, top_k=top_k)
            context = "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(result.chunks))
            system = (
                "你是企业知识库助手, 基于检索上下文回答问题, 不要编造事实.\n\n"
                f"检索上下文:\n{context or '(无检索结果)'}"
            )
            response = await self._llm.ainvoke(
                [{"role": "system", "content": system}, {"role": "user", "content": item.query}]
            )
            answer = _extract_text(response)
            details.append(
                {
                    "query": item.query,
                    "category": item.category,
                    "keypoint_hit_rate": keypoint_hit_rate(answer, item.answer_keypoints),
                    "keypoint_count": len(item.answer_keypoints),
                    "answer": answer[:300],
                }
            )
        return {
            "summary": {"keypoint_hit_rate": average([d["keypoint_hit_rate"] for d in details])},
            "details": details,
        }

    # ── 工具调用准确率评测(静态) ──

    @staticmethod
    def run_tool_fc(
        predicted_calls: list[list[str]], expected_calls: list[list[str]]
    ) -> dict[str, Any]:
        """工具调用准确率: 预测工具名序列 vs 期望序列(逐条对齐)."""
        rate = fc_accuracy(predicted_calls, expected_calls)
        return {"fc_accuracy": rate, "samples": len(expected_calls)}


def _extract_text(obj: Any) -> str:
    """从 LLM 响应提取文本: 兼容 str 与 langchain 消息对象."""
    if isinstance(obj, str):
        return obj
    content = getattr(obj, "content", None)
    return str(content) if content is not None else ""
