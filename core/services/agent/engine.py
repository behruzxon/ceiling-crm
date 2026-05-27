"""
core.services.agent.engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rule-chain decision engine — Phase 1D.

Evaluates :class:`~core.services.agent.rules.AgentRule` instances in
ascending ``priority`` order.  The first rule whose ``matches()`` returns
``True`` gets to ``decide()``; its actions are returned to the caller.
If no rule matches, the engine returns an empty list (no-op).

Import constraints
------------------
  - ``core.services.agent`` siblings only
  - NO imports from ``apps/`` or ``infrastructure/``
"""

from __future__ import annotations

from core.services.agent.base import AgentAction, AgentContext, AgentTrigger
from core.services.agent.rules import (
    AgentRule,
    CatalogFollowupRule,
    ClosingWindowRule,
    DefaultLLMRule,
    FollowupDueRule,
    InactivityRule,
    LeadCreatedRule,
    ObjectionRule,
    OrderDropoffRule,
    PhoneCapturedRule,
    StaleLeadRule,
)
from shared.logging import get_logger

log = get_logger(__name__)


# ── Default rule set ──────────────────────────────────────────────────────────


def _default_rules() -> list[AgentRule]:
    """Return the built-in rule set.

    Phase 2H: StaleLeadRule (35), LeadCreatedRule (40),
    PhoneCapturedRule (45), ObjectionRule (50), FollowupDueRule (55),
    ClosingWindowRule (60), OrderDropoffRule (65),
    CatalogFollowupRule (70), InactivityRule (75), DefaultLLMRule (90).
    Sorted by engine at init time.
    """
    return [
        StaleLeadRule(),
        LeadCreatedRule(),
        PhoneCapturedRule(),
        ObjectionRule(),
        FollowupDueRule(),
        ClosingWindowRule(),
        OrderDropoffRule(),
        CatalogFollowupRule(),
        InactivityRule(),
        DefaultLLMRule(),
    ]


# ── Engine ────────────────────────────────────────────────────────────────────


class AgentDecisionEngine:
    """Priority-ordered, first-match rule evaluator.

    Parameters
    ----------
    rules:
        Custom rule list.  When ``None`` the built-in default set is
        used (see :func:`_default_rules`).
    """

    def __init__(self, rules: list[AgentRule] | None = None) -> None:
        src = rules if rules is not None else _default_rules()
        self._rules: list[AgentRule] = sorted(src, key=lambda r: r.priority)

    async def evaluate(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        """Run rules in priority order; return actions from the first match.

        Returns an empty list when no rule matches.
        """
        for rule in self._rules:
            if rule.matches(trigger, context):
                actions = await rule.decide(trigger, context)
                log.info(
                    "agent_decision",
                    trigger=trigger.value,
                    user_id=context.user_id,
                    lead_id=context.lead_id,
                    rule=type(rule).__name__,
                    action_types=[a.type for a in actions],
                    action_count=len(actions),
                )
                return actions
        log.debug(
            "agent_decision_no_match",
            trigger=trigger.value,
            user_id=context.user_id,
            lead_id=context.lead_id,
        )
        return []
