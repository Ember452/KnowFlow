"""工具基类 - BaseTool 抽象与统一返回结构.

每个工具声明 name/description/domain(执行域)/requires(依赖工具), 提供 input_schema
(返回 JSON Schema) 与 execute(异步执行). 统一返回 ToolResult(success/output/tokens/
latency), 供 metrics 统计与 trace 记录.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from knowflow.core.constants import ExecutionDomain


class ToolResult(BaseModel):
    """工具执行结果. 统一返回结构, 供指标统计与 trace 落库."""

    tool_name: str
    success: bool = True
    output: Any = None
    token_usage: int = 0
    latency_ms: float = 0.0
    error: str | None = None


@dataclass(frozen=True)
class ToolDef:
    """工具定义(扁平化). 用于可见性计算与 schema 注入, 不持有执行能力."""

    name: str
    description: str
    domain: ExecutionDomain
    input_schema: dict[str, Any] = field(default_factory=dict)
    requires: tuple[str, ...] = ()

    def schema_size_chars(self) -> int:
        """schema 字符数(用于 Token 估算的近似量)."""
        import json

        return len(json.dumps(self.input_schema, ensure_ascii=False))


class BaseTool(ABC):
    """工具抽象基类. 子类实现 input_schema 与 execute."""

    name: str = ""
    description: str = ""
    domain: ExecutionDomain = ExecutionDomain.SKILL_ONLY
    requires: tuple[str, ...] = ()  # 依赖的其他工具名(用于拓扑排序/循环检测)

    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """返回输入参数的 JSON Schema(OpenAI function parameters 格式)."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具. 入参由 schema 约束, 返回 ToolResult."""

    def to_def(self) -> ToolDef:
        """转为工具定义(用于可见性计算与注入)."""
        return ToolDef(
            name=self.name,
            description=self.description,
            domain=self.domain,
            input_schema=self.input_schema(),
            requires=self.requires,
        )
