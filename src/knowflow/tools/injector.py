"""工具注入器 - 将可见工具集构建为 LLM tools 参数(JSON Schema 注入).

inject(visible_tools) → OpenAI function-calling 格式的 tools 列表:
    [{"type": "function", "function": {"name", "description", "parameters"}}]
schema_tokens() 用字符数近似估算注入 schema 的 Token 占用(用于指标统计).
"""

import json

from knowflow.tools.base import ToolDef


class Injector:
    """构建 LLM tools 参数与 schema token 估算."""

    def inject(self, visible_tools: list[ToolDef]) -> list[dict[str, object]]:
        """将可见工具转为 OpenAI tools 参数格式."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in visible_tools
        ]

    def schema_chars(self, visible_tools: list[ToolDef]) -> int:
        """注入 schema 的总字符数(含 name/description/parameters)."""
        tools = self.inject(visible_tools)
        return len(json.dumps(tools, ensure_ascii=False))

    def schema_tokens(self, visible_tools: list[ToolDef], chars_per_token: int = 4) -> int:
        """注入 schema 的 Token 估算(字符数 / 4, 近似英文 Token 量)."""
        return self.schema_chars(visible_tools) // chars_per_token
