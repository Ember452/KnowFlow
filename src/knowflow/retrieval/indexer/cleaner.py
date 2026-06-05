"""文本清洗 - 规范化空白与剥离噪声字符.

被所有 parser 调用, 保证解析后的纯文本进入 splitter 前格式一致.
"""

import re

# 零宽字符与 BOM: U+200B (零宽空格) / U+FEFF (BOM) / U+200C/200D (零宽非连接符)
_ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
# 连续空白(含全角空格 \u3000)折叠为单空格
_MULTISPACE_RE = re.compile(r"[ \t\u3000]+")
# 3 个以上换行折叠为 2 个
_MULTINEWLINE_RE = re.compile(r"\n{3,}")


def clean(text: str) -> str:
    """规范化文本.

    步骤: 剥离零宽 -> 统一换行 -> 全角空格统一半角 -> 行内多空格折叠 -> 多换行折叠 -> 行首尾空白.
    纯空白输入返回空字符串.
    """
    if not text:
        return ""
    # 剥离零宽字符与 BOM
    text = _ZERO_WIDTH_RE.sub("", text)
    # 统一换行符: \r\n -> \n, 单独 \r -> \n(Windows/老 Mac 文件兼容)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 全角空格 -> 半角空格, 统一后续折叠
    text = text.replace("\u3000", " ")
    # 行内多空格折叠为单空格
    text = _MULTISPACE_RE.sub(" ", text)
    # 多换行折叠(保留段落结构, 最多 2 个换行)
    text = _MULTINEWLINE_RE.sub("\n\n", text)
    # 按行去首尾空白
    text = "\n".join(line.strip() for line in text.split("\n"))
    # 整体首尾空白
    return text.strip()
