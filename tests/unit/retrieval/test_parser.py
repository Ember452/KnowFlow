"""parser 单测 - 四类分发 / 不支持类型 / 解析结果清洗.

样本文件在 tmp_path 中动态生成, 避免二进制入库.
"""

from pathlib import Path

import pytest

from knowflow.retrieval.indexer import parser
from knowflow.retrieval.indexer.parser import UnsupportedFileTypeError


def test_parse_txt(tmp_path: Path) -> None:
    """txt 文件应被解析并清洗."""
    f = tmp_path / "sample.txt"
    f.write_text("hello   world\n\n\n\nfoo", encoding="utf-8")
    assert parser.parse(f) == "hello world\n\nfoo"


def test_parse_md(tmp_path: Path) -> None:
    """md 文件应去标签并清洗."""
    f = tmp_path / "sample.md"
    f.write_text("# Title\n\npara **bold**\n", encoding="utf-8")
    # markdown 渲染为 <h1>Title</h1><p>para <strong>bold</strong></p>, 剥标签后含 Title/para/bold
    result = parser.parse(f)
    assert "Title" in result
    assert "para" in result
    assert "bold" in result
    assert "<" not in result


def test_parse_pdf(tmp_path: Path) -> None:
    """pdf 文件应逐页取文本. 用 pymupdf 现场生成一个极简 PDF."""
    fitz = pytest.importorskip("fitz")  # 跳过若 pymupdf 未安装
    f = tmp_path / "sample.pdf"
    doc = fitz.open()  # type: ignore[attr-defined]
    page = doc.new_page()
    page.insert_text((72, 72), "hello pdf world")
    doc.save(str(f))
    doc.close()
    result = parser.parse(f)
    assert "hello" in result
    assert "pdf" in result


def test_parse_docx(tmp_path: Path) -> None:
    """docx 文件应拼接段落. 用 python-docx 现场生成."""
    docx_mod = pytest.importorskip("docx")
    f = tmp_path / "sample.docx"
    doc = docx_mod.Document()
    doc.add_paragraph("first paragraph")
    doc.add_paragraph("second paragraph")
    doc.save(str(f))
    result = parser.parse(f)
    assert "first paragraph" in result
    assert "second paragraph" in result


def test_parse_unsupported(tmp_path: Path) -> None:
    """不支持的扩展名应抛 UnsupportedFileTypeError."""
    f = tmp_path / "sample.unknown"
    f.write_text("xxx", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError) as exc_info:
        parser.parse(f)
    assert exc_info.value.error_code == "RETR-001"
    assert "不支持" in exc_info.value.message


def test_parse_no_extension(tmp_path: Path) -> None:
    """无扩展名应抛 UnsupportedFileTypeError."""
    f = tmp_path / "noext"
    f.write_text("xxx", encoding="utf-8")
    with pytest.raises(UnsupportedFileTypeError):
        parser.parse(f)


def test_parse_case_insensitive_ext(tmp_path: Path) -> None:
    """扩展名大小写不敏感."""
    f = tmp_path / "sample.TXT"
    f.write_text("hello   world", encoding="utf-8")
    assert parser.parse(f) == "hello world"
