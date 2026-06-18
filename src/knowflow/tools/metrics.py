"""工具调用指标统计 - 记录每次调用, 提供可见数/Schema Token/FC 准确率统计.

record_call(tool_name, success, tokens, latency): 累计调用记录.
stats(): 返回总调用数/成功率/平均 token/平均耗时.
snapshot(visible_count, schema_tokens, fc_correct, scenario): 记录一次"注入快照",
用于 benchmark 脚本统计执行域隔离前后的可见工具数与 Schema Token, 以及 FC 准确率.
"""

from dataclasses import dataclass, field

from knowflow.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CallRecord:
    """单次工具调用记录."""

    tool_name: str
    success: bool
    token_usage: int
    latency_ms: float


@dataclass
class InjectSnapshot:
    """一次注入场景的指标快照."""

    visible_count: int
    schema_tokens: int
    fc_correct: bool
    scenario: str = ""


@dataclass
class ToolMetrics:
    """工具治理指标收集器."""

    calls: list[CallRecord] = field(default_factory=list)
    snapshots: list[InjectSnapshot] = field(default_factory=list)

    def record_call(
        self, tool_name: str, success: bool, tokens: int = 0, latency_ms: float = 0.0
    ) -> None:
        self.calls.append(
            CallRecord(
                tool_name=tool_name, success=success, token_usage=tokens, latency_ms=latency_ms
            )
        )

    def snapshot(
        self, visible_count: int, schema_tokens: int, fc_correct: bool, scenario: str = ""
    ) -> None:
        self.snapshots.append(
            InjectSnapshot(
                visible_count=visible_count,
                schema_tokens=schema_tokens,
                fc_correct=fc_correct,
                scenario=scenario,
            )
        )

    def call_stats(self) -> dict[str, object]:
        """调用级统计: 总数/成功率/平均 token/平均耗时."""
        total = len(self.calls)
        if total == 0:
            return {"total_calls": 0, "success_rate": 0.0, "avg_tokens": 0, "avg_latency_ms": 0.0}
        success = sum(1 for c in self.calls if c.success)
        return {
            "total_calls": total,
            "success_rate": round(success / total, 4),
            "avg_tokens": round(sum(c.token_usage for c in self.calls) / total, 2),
            "avg_latency_ms": round(sum(c.latency_ms for c in self.calls) / total, 2),
        }

    def governance_stats(self) -> dict[str, object]:
        """治理级统计: 可见工具数均值/Schema Token 均值/FC 准确率."""
        n = len(self.snapshots)
        if n == 0:
            return {
                "avg_visible_count": 0.0,
                "avg_schema_tokens": 0.0,
                "fc_accuracy": 0.0,
                "scenarios": 0,
            }
        avg_visible = sum(s.visible_count for s in self.snapshots) / n
        avg_tokens = sum(s.schema_tokens for s in self.snapshots) / n
        correct = sum(1 for s in self.snapshots if s.fc_correct)
        return {
            "avg_visible_count": round(avg_visible, 2),
            "avg_schema_tokens": round(avg_tokens, 2),
            "fc_accuracy": round(correct / n, 4),
            "scenarios": n,
        }
