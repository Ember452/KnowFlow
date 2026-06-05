"""cleaner 单测 - 空白折叠 / 零宽字符剥离 / 纯空白输入."""

from knowflow.retrieval.indexer.cleaner import clean


def test_clean_empty() -> None:
    """空字符串与 None 输入返回空串."""
    assert clean("") == ""


def test_clean_strips_zero_width() -> None:
    """零宽字符与 BOM 应被剥离."""
    text = "hello\u200bworld\ufeff"
    assert clean(text) == "helloworld"


def test_clean_folds_multispace() -> None:
    """行内多空格折叠为单空格, 含全角空格."""
    assert clean("a    b") == "a b"
    assert clean("a\u3000\u3000b") == "a b"
    assert clean("a\t\tb") == "a b"


def test_clean_folds_multinewline() -> None:
    """3+ 换行折叠为 2 个, 保留段落结构."""
    assert clean("a\n\n\n\nb") == "a\n\nb"
    assert clean("a\n\nb") == "a\n\nb"


def test_clean_strips_line_ends() -> None:
    """行首尾空白被剥离."""
    assert clean("  a  \n  b  ") == "a\nb"


def test_clean_pure_whitespace() -> None:
    """纯空白输入返回空串."""
    assert clean("   \n\n  \t  ") == ""
