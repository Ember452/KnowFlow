"""上下文预算分配 - 系统/历史/工具/检索/记忆各模块配额.

总量 = context_budget_tokens, 按固定比例划分; 各模块超配额时由策略层
(摘要/卸载/截断)处理. 比例可调, 保证检索与记忆在长会话中不被历史挤占.
"""

from knowflow.core.config import Settings, get_settings

# 各模块配额占总量比例(和约等于 1)
BUDGET_RATIOS: dict[str, float] = {
    "system": 0.10,
    "history": 0.35,
    "tools": 0.20,
    "retrieval": 0.25,
    "memory": 0.10,
}


class BudgetManager:
    """上下文预算管理器: 按模块查询配额与超限判定."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._total = self._settings.context_budget_tokens

    @property
    def total(self) -> int:
        return self._total

    def quota(self, module: str) -> int:
        """模块预算 token 数; 未知模块返回 0."""
        ratio = BUDGET_RATIOS.get(module, 0.0)
        return int(self._total * ratio)

    def quotas(self) -> dict[str, int]:
        """全部模块预算(含总量)."""
        return {name: self.quota(name) for name in BUDGET_RATIOS}

    def exceeds(self, module: str, tokens: int) -> bool:
        """模块已用 token 是否超其配额."""
        return tokens > self.quota(module)
