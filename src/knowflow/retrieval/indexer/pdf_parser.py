"""PDF 解析器 - PyMuPDF (fitz) 逐页取文本."""

from pathlib import Path

import fitz  # PyMuPDF

from knowflow.retrieval.indexer.cleaner import clean


def parse(file_path: Path | str) -> str:
    """解析 PDF 文件为纯文本.

    Args:
        file_path: PDF 文件路径.

    Returns:
        清洗后的纯文本, 页与页之间以空行分隔.
    """
    path = Path(file_path)
    pages: list[str] = []
    # mypy: fitz 类型在 ignore_missing_imports 下推断为 Any, 显式标注
    with fitz.open(path) as doc:
        for page in doc:
            pages.append(page.get_text())
    cleaned: str = clean("\n\n".join(pages))
    return cleaned
