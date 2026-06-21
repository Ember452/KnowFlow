"""上下文预算单测 - 配额分配与超限判定."""

from knowflow.context.budget import BUDGET_RATIOS, BudgetManager
from knowflow.core.config import Settings


def test_quotas_follow_ratios() -> None:
    """各模块配额按比例分配, 总和不超过总量."""
    settings = Settings(context_budget_tokens=32000)
    budget = BudgetManager(settings)
    assert budget.total == 32000
    for module, ratio in BUDGET_RATIOS.items():
        assert budget.quota(module) == int(32000 * ratio)
    assert sum(budget.quotas().values()) <= 32000


def test_exceeds_detects_over_quota() -> None:
    settings = Settings(context_budget_tokens=1000)
    budget = BudgetManager(settings)
    history_quota = budget.quota("history")
    assert budget.exceeds("history", history_quota + 1) is True
    assert budget.exceeds("history", history_quota) is False


def test_unknown_module_quota_zero() -> None:
    budget = BudgetManager(Settings())
    assert budget.quota("unknown") == 0
