"""文档解析调度器 - 按文件扩展名分发到具体解析器.

支持的类型: .pdf / .docx / .md / .txt. 其他类型抛 UnsupportedFileTypeError.
"""

from pathlib import Path

from knowflow.core.exceptions import AppError

# 扩展名 -> 解析器模块的映射(延迟导入避免模块加载循环)
_EXT_HANDLERS = {
    ".pdf": "knowflow.retrieval.indexer.pdf_parser",
    ".docx": "knowflow.retrieval.indexer.docx_parser",
    ".md": "knowflow.retrieval.indexer.markdown_parser",
    ".markdown": "knowflow.retrieval.indexer.markdown_parser",
    ".txt": "knowflow.retrieval.indexer.text_parser",
}


class UnsupportedFileTypeError(AppError):
    """不支持的文件类型."""

    error_code = "RETR-001"
    status_code = 422
    default_message = "不支持的文件类型"


def parse(file_path: Path | str) -> str:
    """按扩展名分发到具体解析器.

    Args:
        file_path: 文件路径. .txt/.md 直接读取内容; .pdf/.docx 由对应库解析.

    Returns:
        清洗后的纯文本.

    Raises:
        UnsupportedFileTypeError: 扩展名不在支持列表.
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    handler_module = _EXT_HANDLERS.get(ext)
    if handler_module is None:
        raise UnsupportedFileTypeError(
            f"不支持的文件类型: {ext or '(无扩展名)'}, 支持: {sorted(_EXT_HANDLERS.keys())}"
        )

    # 延迟导入: 仅在需要时加载对应库(如 pymupdf 较重)
    import importlib

    module = importlib.import_module(handler_module)
    if ext in (".txt",):
        # text_parser.parse 接收 bytes/str, 从文件读取
        result: str = module.parse(path.read_bytes())
        return result
    if ext in (".md", ".markdown"):
        md_result: str = module.parse(path.read_text(encoding="utf-8"))
        return md_result
    # pdf / docx 接收路径
    path_result: str = module.parse(path)
    return path_result
