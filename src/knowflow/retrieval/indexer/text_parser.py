"""纯文本解析器 - 直接解码并清洗."""

from knowflow.retrieval.indexer.cleaner import clean


def parse(content: bytes | str, *, encoding: str = "utf-8") -> str:
    """解析纯文本.

    Args:
        content: 字节流或字符串.
        encoding: 字节流解码编码, 默认 utf-8.

    Returns:
        清洗后的纯文本.
    """
    text = content.decode(encoding, errors="replace") if isinstance(content, bytes) else content
    cleaned: str = clean(text)
    return cleaned
