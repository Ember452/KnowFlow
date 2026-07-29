"""章节撰写器 - 按证据包撰写章节正文, 强制 [n] 引用标注.

引用规范: 证据列表以全局下标 [n] 呈现, 模型只允许引用列表内下标,
正文中 [n] 与证据一一对应(Reviewer 据此校验, 防幻觉).
"""

from typing import Any

from knowflow.agents.report.models import Evidence
from knowflow.agents.report.planner import _extract_text
from knowflow.core.config import Settings, get_settings
from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_WRITER_SYSTEM_PROMPT = (
    "你是 KnowFlow 研究报告撰写专家. 根据章节标题与证据素材撰写章节正文.\n"
    "引用规范(必须遵守):\n"
    "- 证据素材以 [n] 标注, n 是证据全局下标; 正文中陈述事实/数据/结论时必须标注 [n];\n"
    "- 只允许引用素材列表中真实存在的 [n], 不得编造下标或内容;\n"
    "- 每段至少引用 1 处证据, 观点与证据一一对应.\n"
    "输出 Markdown 正文(不要标题行, 不要多余说明)."
)

# 无证据模式(needs_research=false 跳过检索): 基于模型知识撰写, 禁止编造 [n] 引用
_WRITER_NO_EVIDENCE_PROMPT = (
    "你是 KnowFlow 研究报告撰写专家. 根据章节标题撰写章节正文.\n"
    "本报告判定无需检索外部资料, 请基于你的既有知识完成撰写;\n"
    "正文中不得出现 [n] 形式的引用标注. 输出 Markdown 正文(不要标题行, 不要多余说明)."
)


class Writer:
    """章节撰写器: 注入章节标题 + 该章证据 + 引用规范, 输出正文."""

    def __init__(self, llm: Any | None = None, settings: Settings | None = None) -> None:
        self._llm = llm
        self._settings = settings or get_settings()

    def _get_llm(self) -> Any:
        if self._llm is not None:
            return self._llm
        from knowflow.core.llm import get_chat_llm

        return get_chat_llm()

    async def write_chapter(
        self,
        chapter: str,
        evidence: list[Evidence],
        base_index: int = 1,
        issues: list[str] | None = None,
    ) -> str:
        """撰写单章节正文.

        Args:
            chapter: 章节标题.
            evidence: 该章节证据列表(与全局证据包同序, base_index 为起始下标);
                为空时启用无证据模式(基于模型知识撰写, 不要求 [n] 引用).
            base_index: 全局起始下标(1-based; 默认 1).
            issues: 上次审查问题清单(重写时传入, 要求针对性修正).

        Returns:
            章节正文(Markdown); LLM 失败返回空串(由流水线降级).
        """
        evidence_lines = "\n".join(
            f"[{base_index + i}] [{ev.source.value}] {ev.title}: {ev.content}"
            for i, ev in enumerate(evidence)
        )
        prompt = _WRITER_NO_EVIDENCE_PROMPT if not evidence else _WRITER_SYSTEM_PROMPT
        if issues:
            issue_text = "\n".join(f"- {issue}" for issue in issues)
            user_content = (
                f"章节标题: {chapter}\n\n证据素材:\n{evidence_lines}\n\n"
                f"上次审查未通过的问题(必须逐条修正):\n{issue_text}\n\n请重写章节正文."
            )
        else:
            user_content = f"章节标题: {chapter}\n\n证据素材:\n{evidence_lines}\n\n请撰写章节正文."
        try:
            response = await self._get_llm().ainvoke(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ]
            )
            return _extract_text(response).strip()
        except Exception as exc:
            logger.warning("report.writer_failed", chapter=chapter, error=str(exc))
            return ""
