"""工具治理端点 - 治理统计面板数据.

GET /tools/stats 返回: 工具总量 / 主 Agent 可见工具数 / 注入 Schema Token /
FC 准确率 / 执行域分布 / 逐工具调用指标.

可见数与 Schema Token 按"全部激活 Skill + 主 Agent 角色"静态计算(治理基线);
FC 准确率与逐工具指标来自 orchestrator 单例内的 ToolMetrics 运行时采集.
"""

import contextlib
from dataclasses import dataclass

from fastapi import APIRouter

from knowflow.api.deps import OrchestratorDep, SkillManagerDep, ToolRegistryDep
from knowflow.core.constants import ExecutionDomain
from knowflow.schemas.tool import ToolGovernanceStats, ToolMetricInfo
from knowflow.tools.domain import AgentRole
from knowflow.tools.injector import Injector
from knowflow.tools.metrics import ToolMetrics
from knowflow.tools.visibility import VisibilityCalculator

router = APIRouter(prefix="/tools", tags=["tools"])


@dataclass
class _CallAgg:
    """单工具调用聚合中间态."""

    calls: int = 0
    success: int = 0
    tokens: int = 0
    latency: float = 0.0


def _aggregate_calls(metrics: ToolMetrics, registry: ToolRegistryDep) -> list[ToolMetricInfo]:
    """按工具聚合调用记录为逐工具指标(按调用次数降序)."""
    by_tool: dict[str, _CallAgg] = {}
    for c in metrics.calls:
        rec = by_tool.setdefault(c.tool_name, _CallAgg())
        rec.calls += 1
        rec.success += 1 if c.success else 0
        rec.tokens += c.token_usage
        rec.latency += c.latency_ms

    result: list[ToolMetricInfo] = []
    for name, rec in by_tool.items():
        domain = "unknown"
        with contextlib.suppress(Exception):
            domain = registry.get(name).domain.value
        result.append(
            ToolMetricInfo(
                tool=name,
                calls=rec.calls,
                success_rate=round(rec.success / rec.calls, 4),
                avg_latency_ms=round(rec.latency / rec.calls, 2),
                token_count=rec.tokens,
                domain=domain,
            )
        )
    return sorted(result, key=lambda m: m.calls, reverse=True)


@router.get("/stats", response_model=ToolGovernanceStats)
async def tool_stats(
    registry: ToolRegistryDep,
    skill_manager: SkillManagerDep,
    orchestrator: OrchestratorDep,
) -> ToolGovernanceStats:
    """工具治理统计: 总量/可见数/Schema Token/FC 准确率/域分布/逐工具指标."""
    tools = registry.list_all()
    breakdown = {d.value: 0 for d in ExecutionDomain}
    for t in tools:
        breakdown[t.domain.value] += 1

    # 治理基线: 全部激活 Skill + 主 Agent 角色下的可见工具集与注入 Schema Token
    visible = VisibilityCalculator().compute(
        skill_manager.active_skills(), AgentRole.MAIN, registry
    )
    visible_tools = len(visible)
    schema_tokens = Injector().schema_tokens(visible)

    # 运行时指标: orchestrator 单例内的 ToolMetrics(未就绪时为 0)
    accuracy = 0.0
    metrics: list[ToolMetricInfo] = []
    if orchestrator is not None:
        m = orchestrator.metrics
        accuracy = float(m.governance_stats()["fc_accuracy"])
        metrics = _aggregate_calls(m, registry)

    return ToolGovernanceStats(
        total_tools=len(tools),
        visible_tools=visible_tools,
        schema_tokens=schema_tokens,
        accuracy=accuracy,
        domain_breakdown=breakdown,
        metrics=metrics,
    )
