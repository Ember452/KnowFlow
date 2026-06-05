"""递归字符分块 - 按优先级分隔符递归切分到 chunk_size 内, 保留 overlap.

分隔符优先级: `\n\n` -> `\n` -> `。` -> 空格. 切到 chunk_size 以内则停止递归;
无法再切(单个分隔符以下文本仍超长)时, 按 chunk_size 硬切. 相邻分块保留 overlap
字符, 保证上下文连续性.
"""

from knowflow.core.exceptions import ValidationError

# 分隔符优先级(高 -> 低): 段落 -> 行 -> 句 -> 词
_SEPARATORS: tuple[str, ...] = ("\n\n", "\n", "。", " ")


def split(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """递归字符分块.

    Args:
        text: 已清洗的纯文本.
        chunk_size: 单块最大字符数.
        overlap: 相邻块重叠字符数, 必须 < chunk_size.

    Returns:
        分块列表, 空输入返回空列表.

    Raises:
        ValidationError: chunk_size <= 0 或 overlap < 0 或 overlap >= chunk_size.
    """
    if chunk_size <= 0:
        raise ValidationError(f"chunk_size 必须 > 0, 实际: {chunk_size}")
    if overlap < 0:
        raise ValidationError(f"overlap 必须 >= 0, 实际: {overlap}")
    if overlap >= chunk_size:
        raise ValidationError(
            f"overlap({overlap}) 必须 < chunk_size({chunk_size}), 否则会产生无限循环"
        )

    if not text:
        return []

    # 短文本直接返回单个分块
    if len(text) <= chunk_size:
        return [text]

    # 递归切分: 得到所有"原始片段"(尚未应用 overlap)
    raw_chunks = _recursive_split(text, chunk_size, _SEPARATORS)

    # 应用 overlap: 第 i 块(i>0)前缀拼上第 i-1 块末尾 overlap 字符
    if overlap == 0 or len(raw_chunks) <= 1:
        return raw_chunks

    merged: list[str] = [raw_chunks[0]]
    for i in range(1, len(raw_chunks)):
        prev_tail = raw_chunks[i - 1][-overlap:]
        cur = raw_chunks[i]
        # 拼接后不超过 chunk_size 才加前缀, 否则保留原块(避免膨胀)
        if len(prev_tail) + len(cur) <= chunk_size:
            merged.append(prev_tail + cur)
        else:
            merged.append(cur)
    return merged


def _recursive_split(text: str, chunk_size: int, separators: tuple[str, ...]) -> list[str]:
    """递归按分隔符切分.

    优先用第一个分隔符切分; 若切出来的片段仍超长, 对超长片段用下一个分隔符递归;
    所有分隔符用完仍超长, 按 chunk_size 硬切.
    """
    if len(text) <= chunk_size:
        return [text]

    # 没有可用分隔符了, 硬切
    if not separators:
        return _hard_split(text, chunk_size)

    sep = separators[0]
    rest_seps = separators[1:]
    parts = text.split(sep)

    # 当前分隔符未切出多段(文本中无此分隔符), 退到下一个分隔符
    if len(parts) == 1:
        return _recursive_split(text, chunk_size, rest_seps)

    # 贪心合并: 把相邻小片段拼到 chunk_size 以内, 超长的递归再切
    # 分隔符保留在前一块末尾(不丢失语义边界, 与 LangChain 惯例一致)
    result: list[str] = []
    buffer = ""

    def _flush() -> None:
        nonlocal buffer
        if not buffer:
            return
        # 中间块: 尾部追加 sep(若不超 chunk_size), 保留语义边界
        flushed = buffer + sep if len(buffer) + len(sep) <= chunk_size else buffer
        result.append(flushed)
        buffer = ""

    for part in parts:
        # 单个 part 自身超长: 先 flush buffer, 再递归切分 part
        if len(part) > chunk_size:
            _flush()
            sub = _recursive_split(part, chunk_size, rest_seps)
            result.extend(sub[:-1])
            buffer = sub[-1] if sub else ""
            continue

        # 尝试把 part 并入 buffer
        if buffer:
            candidate = buffer + sep + part
            if len(candidate) <= chunk_size:
                buffer = candidate
            else:
                # 装不下, flush 当前 buffer, part 作为新 buffer 起点
                _flush()
                buffer = part
        else:
            buffer = part

    # 最后一块不再追加 sep(已是原文结尾)
    if buffer:
        result.append(buffer)

    return result


def _hard_split(text: str, chunk_size: int) -> list[str]:
    """所有分隔符都无法切时, 按 chunk_size 硬切."""
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
