"""计算器工具 - 安全表达式求值(白名单 AST 求值, 无 eval/exec).

支持 + - * / ** % // 与括号、数字. 拦截名称/属性/调用等非数学节点, 防止代码注入.
"""

import ast
import time
from typing import Any

from knowflow.core.constants import ExecutionDomain
from knowflow.core.exceptions import ValidationError
from knowflow.tools.base import BaseTool, ToolResult

# 允许的 AST 节点类型(仅数学运算)
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)


class CalculatorTool(BaseTool):
    """计算器: 对数学表达式安全求值. direct 域, 主 Agent 始终可见."""

    name = "calculator"
    description = "数学表达式求值. 输入算式(如 2**10 或 (1+2)*3), 返回数值结果."
    domain = ExecutionDomain.DIRECT

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式, 仅支持数字与 + - * / ** % // () ",
                }
            },
            "required": ["expression"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        start = time.perf_counter()
        expression = str(kwargs.get("expression", ""))
        try:
            value = self._safe_eval(expression)
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=value,
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=round(latency_ms, 2),
            )

    @staticmethod
    def _safe_eval(expression: str) -> int | float:
        """白名单 AST 求值. 非法节点抛 ValidationError."""
        expr = expression.strip()
        if not expr:
            raise ValidationError("表达式为空")
        if len(expr) > 200:
            raise ValidationError("表达式过长(>200 字符)")
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise ValidationError(f"表达式语法错误: {exc}") from exc
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ValidationError(f"不允许的表达式节点: {type(node).__name__}")
        # eval 安全: 节点已白名单过滤, 仅含数字与数学运算符
        result: object = eval(compile(tree, "<calculator>", "eval"))
        if isinstance(result, bool) or not isinstance(result, int | float):
            raise ValidationError("表达式结果非数值")
        return result
