"""DOCX 解析器 - python-docx 拼接段落."""

from pathlib import Path

from docx import Document

from knowflow.retrieval.indexer.cleaner import clean


def parse(file_path: Path | str) -> str:
    """解析 DOCX 文件为纯文本.

    Args:
        file_path: DOCX 文件路径.

    Returns:
        清洗后的纯文本, 段落之间以换行分隔.
    """
    path = Path(file_path)
    doc = Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    cleaned: str = clean("\n".join(paragraphs))
    return cleaned
