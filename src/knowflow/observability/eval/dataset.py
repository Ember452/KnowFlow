"""评测数据集加载与校验.

支持两种格式(jsonl, 每行一个 JSON 对象):
- retrieval:   {"query", "doc_ids", "category"} 文档级检索标注
- knowledge_qa: {"query", "answer_keypoints", "related_chunks", "category"} QA 标注
  (answer_keypoints 为参考答案要点片段, 用于自动化的要点命中率评测)
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EvalItem:
    """单条评测样本."""

    query: str
    category: str = "general"
    doc_ids: list[int] = field(default_factory=list)  # retrieval: 相关文档
    answer_keypoints: list[str] = field(default_factory=list)  # qa: 参考答案要点
    related_chunks: list[int] = field(default_factory=list)  # qa: 相关 chunk id


class EvalDataset:
    """评测集: 加载 jsonl + schema 校验."""

    def __init__(self, name: str, items: Sequence[EvalItem]) -> None:
        self.name = name
        self.items = list(items)

    @classmethod
    def load(cls, path: str | Path, kind: str = "retrieval") -> EvalDataset:
        """从 jsonl 加载评测集. kind: retrieval / knowledge_qa."""
        p = Path(path)
        items: list[EvalItem] = []
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"评测集第 {lineno} 行 JSON 解析失败: {exc}") from exc
            items.append(cls._parse_item(raw, kind, lineno))
        if not items:
            raise ValueError(f"评测集为空: {p}")
        logger.info("eval.dataset_loaded", name=p.stem, kind=kind, count=len(items))
        return cls(p.stem, items)

    @staticmethod
    def _parse_item(raw: dict[str, Any], kind: str, lineno: int) -> EvalItem:
        query = str(raw.get("query", "")).strip()
        if not query:
            raise ValueError(f"评测集第 {lineno} 行缺少 query")
        if kind == "retrieval":
            doc_ids = [int(x) for x in raw.get("doc_ids", [])]
            if not doc_ids:
                raise ValueError(f"评测集第 {lineno} 行缺少 doc_ids")
            return EvalItem(
                query=query, category=str(raw.get("category", "general")), doc_ids=doc_ids
            )
        keypoints = [str(k).strip() for k in raw.get("answer_keypoints", []) if str(k).strip()]
        chunks = [int(x) for x in raw.get("related_chunks", [])]
        if not keypoints:
            raise ValueError(f"评测集第 {lineno} 行缺少 answer_keypoints")
        return EvalItem(
            query=query,
            category=str(raw.get("category", "general")),
            answer_keypoints=keypoints,
            related_chunks=chunks,
        )
