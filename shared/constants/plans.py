"""
shared.constants.plans
~~~~~~~~~~~~~~~~~~~~~~
Central plan configuration defining per-plan limits and feature gates.

Usage:
    from shared.constants.plans import get_plan_config, PLAN_CONFIGS
    config = get_plan_config("pro")
    if config.knowledge_base_enabled: ...
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.constants.enums import SubscriptionPlan


@dataclass(frozen=True, slots=True)
class PlanConfig:
    """Immutable plan definition with limits and feature flags."""

    name: str
    display_name: str
    leads_per_month: int          # 0 = unlimited
    ai_messages_per_day: int      # 0 = unlimited
    knowledge_base_enabled: bool
    operator_assignment_enabled: bool
    analytics_enabled: bool
    monthly_price_uzs: int


PLAN_CONFIGS: dict[str, PlanConfig] = {
    SubscriptionPlan.FREE.value: PlanConfig(
        name="free",
        display_name="Free",
        leads_per_month=50,
        ai_messages_per_day=100,
        knowledge_base_enabled=False,
        operator_assignment_enabled=False,
        analytics_enabled=False,
        monthly_price_uzs=0,
    ),
    SubscriptionPlan.BASIC.value: PlanConfig(
        name="basic",
        display_name="Basic",
        leads_per_month=500,
        ai_messages_per_day=1_000,
        knowledge_base_enabled=True,
        operator_assignment_enabled=False,
        analytics_enabled=False,
        monthly_price_uzs=200_000,
    ),
    SubscriptionPlan.PRO.value: PlanConfig(
        name="pro",
        display_name="Pro",
        leads_per_month=3_000,
        ai_messages_per_day=5_000,
        knowledge_base_enabled=True,
        operator_assignment_enabled=True,
        analytics_enabled=True,
        monthly_price_uzs=500_000,
    ),
    SubscriptionPlan.ENTERPRISE.value: PlanConfig(
        name="enterprise",
        display_name="Enterprise",
        leads_per_month=0,
        ai_messages_per_day=0,
        knowledge_base_enabled=True,
        operator_assignment_enabled=True,
        analytics_enabled=True,
        monthly_price_uzs=1_000_000,
    ),
}

# Default fallback when tenant has no plan or unknown plan
_DEFAULT_PLAN = SubscriptionPlan.FREE.value


def get_plan_config(plan_name: str | None) -> PlanConfig:
    """Return the PlanConfig for the given plan name.

    Falls back to FREE if the plan is unknown or None.
    """
    if not plan_name:
        return PLAN_CONFIGS[_DEFAULT_PLAN]
    return PLAN_CONFIGS.get(plan_name, PLAN_CONFIGS[_DEFAULT_PLAN])
