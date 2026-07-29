"""证据融合器 - 章节证据去重后组织为全局证据包(供 [n] 引用).

去重: 内容近似相似(SequenceMatcher ratio >= 0.9)视为重复, 保留先到者;
证据包保序, 全局下标从 1 开始(与章节正文 [n] 标注一致).
"""

from difflib import SequenceMatcher

from knowflow.agents.report.models import Evidence, EvidencePack

_DEDUP_RATIO = 0.9  # 近似去重阈值


class Synthesizer:
    """证据融合: 去重 → 全局证据包 + 章节→下标映射."""

    def synthesize(self, chapter_evidence: dict[str, list[Evidence]]) -> EvidencePack:
        """聚合全部章节证据为证据包.

        Args:
            chapter_evidence: {章节标题: 证据列表}(Researcher 产出).

        Returns:
            EvidencePack: 全局证据列表 + 章节→全局下标(1-based)映射.
        """
        pack: list[Evidence] = []
        chapter_index: dict[str, list[int]] = {}
        for chapter, evs in chapter_evidence.items():
            indexes: list[int] = []
            for ev in evs:
                if not ev.content.strip():
                    continue
                if self._is_duplicate(ev, pack):
                    continue
                pack.append(ev)
                indexes.append(len(pack))
            chapter_index[chapter] = indexes
        return EvidencePack(evidence=pack, chapter_index=chapter_index)

    @staticmethod
    def _is_duplicate(ev: Evidence, pack: list[Evidence]) -> bool:
        """与已有证据内容近似相似即重复."""
        for existing in pack:
            if SequenceMatcher(None, ev.content, existing.content).ratio() >= _DEDUP_RATIO:
                return True
        return False
