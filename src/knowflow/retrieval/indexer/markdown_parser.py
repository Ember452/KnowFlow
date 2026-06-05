"""Markdown 解析器 - 转纯文本(去标签).

用 markdown 库渲染为 HTML, 再剥离标签保留文本. 适用于 .md 文档.
"""

import re

import markdown as md

from knowflow.retrieval.indexer.cleaner import clean

# 剥离 HTML 标签
_TAG_RE = re.compile(r"<[^>]+>")
# HTML 实体常见转换(最小集, 满足检索语料需求)
_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&nbsp;": " ",
}


def _strip_html(html: str) -> str:
    """剥离 HTML 标签与常见实体."""
    for entity, char in _ENTITIES.items():
        html = html.replace(entity, char)
    return _TAG_RE.sub("", html)


def parse(content: str) -> str:
    """解析 Markdown 为纯文本.

    Args:
        content: Markdown 原始字符串.

    Returns:
        清洗后的纯文本.
    """
    html = md.markdown(content, extensions=["extra"])
    text = _strip_html(html)
    cleaned: str = clean(text)
    return cleaned
