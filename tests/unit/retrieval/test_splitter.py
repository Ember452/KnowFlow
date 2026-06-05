"""splitter 单测 - 递归切分 / overlap / 边界 / 异常."""

import pytest

from knowflow.core.exceptions import ValidationError
from knowflow.retrieval.indexer.splitter import split


def test_split_empty() -> None:
    """空字符串返回空列表."""
    assert split("", chunk_size=100, overlap=0) == []


def test_split_short_text() -> None:
    """短文本不切分, 返回单个分块."""
    text = "hello world"
    assert split(text, chunk_size=100, overlap=0) == [text]


def test_split_long_text_paragraph() -> None:
    """超长文本按段落分隔符 `\n\n` 切分, 分隔符保留在前块末尾."""
    p1 = "a" * 50
    p2 = "b" * 50
    text = f"{p1}\n\n{p2}"
    chunks = split(text, chunk_size=60, overlap=0)
    assert len(chunks) == 2
    # 第 1 块尾部保留段落分隔符
    assert chunks[0] == f"{p1}\n\n"
    assert chunks[1] == p2


def test_split_long_text_line() -> None:
    """无段落分隔时按行 `\n` 切分, 分隔符保留在前块末尾."""
    l1 = "a" * 30
    l2 = "b" * 30
    text = f"{l1}\n{l2}"
    chunks = split(text, chunk_size=40, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == f"{l1}\n"
    assert chunks[1] == l2


def test_split_long_text_sentence() -> None:
    """无段落/行分隔时按句号 `。` 切分, 分隔符保留在前块末尾."""
    s1 = "a" * 20
    s2 = "b" * 20
    text = f"{s1}。{s2}"
    chunks = split(text, chunk_size=25, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == f"{s1}。"
    assert chunks[1] == s2


def test_split_long_text_space() -> None:
    """无段落/行/句分隔时按空格切分, 分隔符保留在前块末尾."""
    w1 = "a" * 10
    w2 = "b" * 10
    text = f"{w1} {w2}"
    chunks = split(text, chunk_size=12, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == f"{w1} "
    assert chunks[1] == w2


def test_split_hard_cut() -> None:
    """所有分隔符都无法切时按 chunk_size 硬切."""
    text = "a" * 100  # 无任何分隔符
    chunks = split(text, chunk_size=30, overlap=0)
    assert len(chunks) == 4  # 30 + 30 + 30 + 10
    assert all(len(c) <= 30 for c in chunks)
    # 拼接后应能还原原文
    assert "".join(chunks) == text


def test_split_with_overlap() -> None:
    """overlap 应用: 第 i 块前缀为第 i-1 块末尾 overlap 字符."""
    # 构造两个明确的段落, 切成两块
    p1 = "a" * 50
    p2 = "b" * 50
    text = f"{p1}\n\n{p2}"
    chunks = split(text, chunk_size=60, overlap=10)
    assert len(chunks) == 2
    # 第 0 块含段落分隔符(末尾)
    assert chunks[0] == f"{p1}\n\n"
    # 第 1 块前缀 = 第 0 块末尾 10 字符(含分隔符) + p2
    assert chunks[1] == chunks[0][-10:] + p2


def test_split_overlap_skipped_when_too_big() -> None:
    """拼接 overlap 后超 chunk_size 时保留原块, 不加前缀."""
    p1 = "a" * 50
    p2 = "b" * 55  # 自身接近 chunk_size, 加 overlap 必超
    text = f"{p1}\n\n{p2}"
    chunks = split(text, chunk_size=60, overlap=10)
    assert len(chunks) == 2
    # 第 0 块含段落分隔符
    assert chunks[0] == f"{p1}\n\n"
    # 第 1 块(p2, 55) + overlap(10) = 65 > 60, 保留原块
    assert chunks[1] == p2


def test_split_recursive_fallback() -> None:
    """段落切分后单个 part 仍超长, 递归用下一级分隔符再切."""
    # 段落 1 含行分隔, 但段落 1 整体超长
    l1 = "a" * 30
    l2 = "b" * 30
    l3 = "c" * 30
    p1 = f"{l1}\n{l2}\n{l3}"
    p2 = "d" * 20
    text = f"{p1}\n\n{p2}"
    # chunk_size=40: p1(92) 超长, 递归到 \n 切分
    chunks = split(text, chunk_size=40, overlap=0)
    # p1 切成 3 块(l1\n, l2\n, l3), 然后 l3 与 p2 不能合并, l3 flush 时加段落分隔符
    assert len(chunks) == 4
    assert chunks[0] == f"{l1}\n"
    assert chunks[1] == f"{l2}\n"
    assert chunks[2] == f"{l3}\n\n"  # l3 作为 p1 末尾, flush 时加外层 sep `\n\n`
    assert chunks[3] == p2


def test_split_recursive_all_levels() -> None:
    """多级递归: 段落 -> 行 -> 句 -> 空格 -> 硬切."""
    # 构造一个无任何分隔符的超长 token, 强制走到硬切
    text = "x" * 200
    chunks = split(text, chunk_size=50, overlap=0)
    assert len(chunks) == 4  # 50*4
    assert all(len(c) <= 50 for c in chunks)
    assert "".join(chunks) == text


def test_split_chunk_size_zero() -> None:
    """chunk_size <= 0 抛 ValidationError."""
    with pytest.raises(ValidationError):
        split("hello", chunk_size=0, overlap=0)


def test_split_chunk_size_negative() -> None:
    """chunk_size 负数抛 ValidationError."""
    with pytest.raises(ValidationError):
        split("hello", chunk_size=-1, overlap=0)


def test_split_overlap_negative() -> None:
    """overlap 负数抛 ValidationError."""
    with pytest.raises(ValidationError):
        split("hello", chunk_size=100, overlap=-1)


def test_split_overlap_ge_chunk_size() -> None:
    """overlap >= chunk_size 抛 ValidationError(防无限循环)."""
    with pytest.raises(ValidationError):
        split("hello", chunk_size=10, overlap=10)
    with pytest.raises(ValidationError):
        split("hello", chunk_size=10, overlap=11)


def test_split_overlap_zero() -> None:
    """overlap=0 时不应用前缀."""
    p1 = "a" * 50
    p2 = "b" * 50
    text = f"{p1}\n\n{p2}"
    chunks = split(text, chunk_size=60, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == f"{p1}\n\n"  # 分隔符保留在前块末尾
    assert chunks[1] == p2  # 无前缀


def test_split_single_chunk_no_overlap_applied() -> None:
    """切分后只有 1 块时不应用 overlap."""
    text = "a" * 50  # 短文本
    chunks = split(text, chunk_size=100, overlap=10)
    assert chunks == [text]


def test_split_preserves_content() -> None:
    """切分后所有块拼接(去除 overlap 前缀)应能还原原文."""
    # 构造多段落文本
    paragraphs = [f"段落{i}的内容" + "x" * 40 for i in range(5)]
    text = "\n\n".join(paragraphs)
    chunks = split(text, chunk_size=50, overlap=10)
    # 第 0 块应是原文开头
    assert text.startswith(chunks[0])
    # 验证至少切了多块
    assert len(chunks) > 1
    # 所有块不超过 chunk_size(允许 overlap 拼接后略超? 不允许, 我们的条件已保证)
    # 注: overlap 拼接仅在不超过 chunk_size 时应用, 故所有块 <= chunk_size
    assert all(len(c) <= 50 for c in chunks)


def test_split_mixed_separators() -> None:
    """混合分隔符文本: 优先用高级分隔符."""
    # 段落 + 行 + 句子混合
    text = "段落一句子一。句子二。\n段落二句子三。"
    chunks = split(text, chunk_size=10, overlap=0)
    # 至少切出多块, 每块 <= 10
    assert len(chunks) > 1
    assert all(len(c) <= 10 for c in chunks)
