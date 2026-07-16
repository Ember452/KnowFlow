"""用户 query 改写 - 多轮对话中指代消解与意图补全, 提升检索召回质量.

仅在有对话历史时改写; LLM 调用失败或输出为空时回退原 query, 不阻塞对话主流程.
"""

from typing import Any

from knowflow.core.logging import get_logger

logger = get_logger(__name__)

_REWRITE_SYSTEM_PROMPT = """你是查询改写助手. 根据对话历史, 把用户当前问题改写为独立、完整、
可直接用于知识库检索的查询.
要求:
1. 补充指代(它/这个/上面/这些等)指向的具体对象
2. 保留原意, 不添加历史中不存在的信息, 不要回答问题
3. 只输出改写后的查询文本, 不要任何解释、引号或前缀"""


class QueryRewriter:
    """多轮查询改写器. 无历史时直接返回原 query(不调用 LLM)."""

    def __init__(self, llm: Any) -> None:
        """初始化.

        Args:
            llm: langchain BaseChatModel 或 fake(实现 async ainvoke).
        """
        self._llm = llm

    async def rewrite(self, query: str, history: list[dict[str, str]]) -> str:
        """改写 query; 单轮/失败/空输出/复读场景回退原 query.

        Args:
            query: 用户当前问题.
            history: 最近对话历史([{"role", "content"}, ...]).

        Returns:
            改写后的独立查询, 或原 query.
        """
        if not history:
            return query
        history_text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in history
        )
        try:
            response = await self._llm.ainvoke(
                [
                    {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"对话历史:\n{history_text}\n\n当前问题: {query}"},
                ]
            )
        except Exception as exc:
            logger.warning("query_rewrite.failed_fallback", error=str(exc))
            return query
        rewritten = self._extract_text(response).strip()
        if not rewritten or rewritten == query:
            return query
        return rewritten[:500]

    @staticmethod
    def _extract_text(response: Any) -> str:
        """从 langchain AIMessage / str / 其他响应中提取文本."""
        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(response, str):
            return response
        return str(content) if content is not None else str(response)
