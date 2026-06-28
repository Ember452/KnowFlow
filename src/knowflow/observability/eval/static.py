"""静态评测组件 - 不依赖真实 LLM/向量库的可复现评测.

FakeRetriever: 查询关键词在语料中匹配句子, chunk_id 使用 chunk_map 中该文档的
首个 chunk id, 使文档级指标可判定; FakeLLM: 返回检索上下文原文拼接.
用于 run_eval.py 静态模式与 POST /eval/run 端点.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CORPUS_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent.parent / "eval" / "datasets" / "corpus"
)

# 文件名 → doc_id(与 compare_baseline 的语料映射一致)
DOC_ID_BY_STEM = {
    "finance_policy": 1,
    "hr_policy": 2,
    "it_sop": 3,
    "ops_runbook": 4,
    "product_manual": 5,
}


class FakeRetriever:
    """静态模式 retriever: 查询关键词在语料中匹配句子作为检索结果."""

    def __init__(self, chunk_map_file: str | Path | None = None) -> None:
        self._doc_first_chunk: dict[int, int] = {}
        if chunk_map_file is not None:
            raw = json.loads(Path(chunk_map_file).read_text(encoding="utf-8"))
            self._doc_first_chunk = {int(k): v[0] for k, v in raw.items()}
        self._corpus_sentences: list[tuple[int, int, str]] = []  # (doc_id, seq, 句子)
        for doc_path in sorted(CORPUS_DIR.glob("*.md")):
            doc_id = DOC_ID_BY_STEM.get(doc_path.stem, 0)
            text = doc_path.read_text(encoding="utf-8")
            for seq, sentence in enumerate(re.split(r"[。\n]", text)):
                sentence = sentence.strip()
                if len(sentence) >= 4:
                    self._corpus_sentences.append((doc_id, seq, sentence))

    async def retrieve(self, query: str, top_k: int = 10) -> Any:
        """按查询关键词匹配语料句子, 返回脚本化结果."""
        keywords = [
            k for k in re.split(r"[的了吗什么怎么多久哪些什么流程制度]", query) if len(k) >= 2
        ]
        scored: list[tuple[int, int, int, str]] = []
        for doc_id, seq, sentence in self._corpus_sentences:
            hits = sum(1 for kw in keywords if kw in sentence)
            if hits:
                scored.append((hits, doc_id, seq, sentence))
        scored.sort(key=lambda x: (-x[0], x[1], x[2]))
        chunks: list[Any] = []
        seen_docs: set[int] = set()
        for hits, doc_id, _, sentence in scored:
            chunk_id = self._doc_first_chunk.get(doc_id)
            if chunk_id is None or chunk_id in seen_docs:
                continue  # 每个相关文档只贡献一个结果, 保持 doc 级判定简洁
            seen_docs.add(chunk_id)
            chunks.append(
                type(
                    "C",
                    (),
                    {"chunk_id": chunk_id, "content": sentence[:200], "score": float(hits)},
                )
            )
            if len(chunks) >= top_k:
                break
        return type("R", (), {"query": query, "chunks": chunks, "latency_ms": 1.0})()


class FakeLLM:
    """静态模式 LLM: 返回检索上下文的原文拼接(模拟基于上下文的回答)."""

    async def ainvoke(self, messages: Any) -> str:
        system = next(m["content"] for m in messages if m["role"] == "system")
        context = system.split("检索上下文:\n", 1)[-1] if "检索上下文:" in system else ""
        return context[:500] or "静态模式无检索结果"
