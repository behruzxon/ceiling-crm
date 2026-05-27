"""
core.services.agent.rules
~~~~~~~~~~~~~~~~~~~~~~~~~~
Agent decision rules — Phase 1D.

Each rule encapsulates a single decision: *when* to act (``matches``)
and *what* to do (``decide``).  Rules are evaluated by
:class:`~core.services.agent.engine.AgentDecisionEngine` in ascending
``priority`` order; the first match wins.

Phase 1D ships a single concrete rule — :class:`CatalogFollowupRule` —
which replaces the inline ``_handle_catalog_open`` that lived in
``AgentOrchestrator`` during Phase 1A.

Import constraints
------------------
  - stdlib + ``core.services.agent.base`` types
  - NO imports from ``apps/`` or ``infrastructure/``
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from core.services.agent.base import AgentAction, AgentContext, AgentTrigger

# ── Abstract rule ─────────────────────────────────────────────────────────────


class AgentRule(ABC):
    """Base class for all agent decision rules.

    Subclasses must set ``priority`` (lower = evaluated earlier) and
    implement ``matches`` + ``decide``.
    """

    priority: int = 100
    """Lower value = higher priority.  Rules are sorted ascending."""

    @abstractmethod
    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        """Return ``True`` if this rule applies to the given trigger + context."""
        ...

    @abstractmethod
    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        """Return zero or more actions to execute.

        Called only when :meth:`matches` returned ``True``.
        """
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}(priority={self.priority})"


# ── Follow-up message variants (moved from base.py) ──────────────────────────

_CATALOG_FOLLOWUP_MESSAGES: tuple[str, ...] = (
    "Katalogni ko'rdingizmi? \U0001f642\n"
    "Xohlasangiz narxni hisoblab beraman yoki tanlashda yordam beraman.",
    "Dizaynlarni ko'rib chiqdingizmi? \U0001f60a\n" "Savollaringiz bo'lsa yozing — yordam beraman!",
    "Katalogdagi dizaynlar yoqdimi? \U0001f642\n"
    "Xona uchun qaysi biri to'g'ri kelishini maslahat bera olaman.",
)


# ── Concrete rules ────────────────────────────────────────────────────────────


class CatalogFollowupRule(AgentRule):
    """Pick a follow-up nudge when the user opened the catalog.

    Mirrors the Phase 1A ``AgentOrchestrator._handle_catalog_open``
    behavior exactly: random message selection, ``type="reply"`` action
    with ``reason="catalog_inactivity_followup"``.
    """

    priority = 70

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.CATALOG_OPEN

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        text = random.choice(_CATALOG_FOLLOWUP_MESSAGES)
        return [
            AgentAction(
                type="reply",
                payload={
                    "text": text,
                    "reason": "catalog_inactivity_followup",
                },
            ),
        ]


class ObjectionRule(AgentRule):
    """Route detected objections through the agent pipeline.

    Phase 2A: delegates to the existing ``_handle_objection`` handler
    via a ``"handle_objection"`` action.  Future phases may insert
    higher-priority negotiation rules that preempt this one.
    """

    priority = 50

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.OBJECTION and context.objection_type is not None

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="handle_objection",
                payload={
                    "objection_type": context.objection_type,
                    "severity": context.objection_severity or "medium",
                },
            ),
        ]


class ClosingWindowRule(AgentRule):
    """Evaluate whether conditions are right for a close attempt.

    Phase 2B: reuses the same 5 triggers as the existing
    ``sales_closer.should_attempt_close()`` function:
      1. Lead score >= 40
      2. LLM intent is price / measurement / catalog
      3. Closing confidence >= 0.6
      4. Phone captured (from memory)
      5. Area known (from memory)

    Returns ``attempt_close`` action when at least one condition is met,
    empty list (skip) otherwise.  The downstream ``attempt_close()``
    still enforces its own Redis NX cooldown — this rule is a pre-filter
    that lets future higher-priority rules preempt closing.
    """

    _SCORE_THRESHOLD = 40
    _CLOSING_INTENTS: frozenset[str] = frozenset({"price", "measurement", "catalog"})
    _CONFIDENCE_THRESHOLD = 0.6

    priority = 60

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.ATTEMPT_CLOSE

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        reason = self._evaluate(context)
        if reason is None:
            return []
        return [
            AgentAction(
                type="attempt_close",
                payload={"reason": reason},
            ),
        ]

    @staticmethod
    def _evaluate(ctx: AgentContext) -> str | None:
        """Return a reason string if at least one closing trigger fires."""
        if ctx.score >= ClosingWindowRule._SCORE_THRESHOLD:
            return "score_threshold"
        if ctx.intent in ClosingWindowRule._CLOSING_INTENTS:
            return "intent_signal"
        if (
            ctx.closing_confidence is not None
            and ctx.closing_confidence >= ClosingWindowRule._CONFIDENCE_THRESHOLD
        ):
            return "high_confidence"
        mem = ctx.memory
        if mem.get("phone_captured"):
            return "phone_captured"
        if mem.get("area_m2") is not None:
            return "area_known"
        return None


class PhoneCapturedRule(AgentRule):
    """Evaluate phone-capture milestone and decide notification action.

    Phase 2D: always returns a ``notify_lead_collected`` action so the
    existing admin notification fires.  Future higher-priority rules may
    preempt this to gate or modify notification behaviour.
    """

    priority = 45

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.PHONE_CAPTURED

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="notify_lead_collected",
                payload={"reason": "phone_captured"},
            ),
        ]


class LeadCreatedRule(AgentRule):
    """React to a lead being committed to the database.

    Phase 2E: always returns a ``notify_new_lead`` action so the
    existing admin notification fires.  Future higher-priority rules may
    preempt this to gate or modify notification behaviour.
    """

    priority = 40

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.LEAD_CREATED

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="notify_new_lead",
                payload={"reason": "lead_created"},
            ),
        ]


class OrderDropoffRule(AgentRule):
    """React to user abandoning a measurement or order FSM mid-flow.

    Phase 2G: returns a ``handle_order_dropoff`` action so the handler
    can log the event for observability.  Future higher-priority rules
    may preempt this to send recovery messages or notifications.
    """

    priority = 65

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.ORDER_DROPOFF

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="handle_order_dropoff",
                payload={"reason": "order_dropoff"},
            ),
        ]


class StaleLeadRule(AgentRule):
    """Evaluate whether a stale lead should be processed (tiered reminders/LOST).

    Phase 2F: always returns a ``process_stale_lead`` action so the
    existing tiered inactivity logic fires.  Future higher-priority rules
    may preempt this to gate or modify stale-lead behaviour.
    """

    priority = 35

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.STALE_LEAD

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="process_stale_lead",
                payload={"reason": "stale_lead"},
            ),
        ]


class FollowupDueRule(AgentRule):
    """Evaluate whether a due follow-up should proceed or be skipped.

    Phase 2C: reuses the same skip logic as the follow-up brain's
    ``_check_skip()`` function:
      1. Follow-up count >= MAX cap (5)
      2. User recently active (< 10 min)
      3. Cold + cooling trend + low score (< 15)

    Returns ``send_followup`` action when the follow-up should proceed,
    empty list (skip) otherwise.  The downstream ``FollowupService``
    still calls the brain for type/delay selection and sends the admin
    card — this rule is a pre-filter only.
    """

    _MAX_FOLLOWUP_COUNT = 5
    _RECENTLY_ACTIVE_SECONDS = 600  # 10 minutes

    priority = 55

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.FOLLOWUP_DUE

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        skip = self._check_skip(context)
        if skip is not None:
            return []
        return [
            AgentAction(
                type="send_followup",
                payload={"reason": "due"},
            ),
        ]

    def _check_skip(self, ctx: AgentContext) -> str | None:
        """Return skip reason string, or None if follow-up should proceed."""
        if ctx.follow_up_count >= self._MAX_FOLLOWUP_COUNT:
            return "cap_reached"

        if ctx.last_activity_ts is not None:
            import time

            elapsed = time.time() - ctx.last_activity_ts
            if elapsed < self._RECENTLY_ACTIVE_SECONDS:
                return "recently_active"

        # Cold + cooling + low score — replicate brain _check_skip
        mem = ctx.memory
        if (
            ctx.lead_temperature == "cold"
            and mem.get("engagement_trend") == "cooling_down"
            and ctx.score < 15
        ):
            return "cold_cooling_low"

        return None


class InactivityRule(AgentRule):
    """Evaluate whether an inactivity CTA should be sent.

    Phase 2H: always returns a ``send_cta`` action so the existing
    inactive_cta.py CTA logic fires.  Future higher-priority rules may
    preempt this to gate or modify CTA behaviour.
    """

    priority = 75

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.INACTIVITY

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="send_cta",
                payload={"reason": "inactivity"},
            ),
        ]


class DefaultLLMRule(AgentRule):
    """Fallback: forward unhandled messages to the OpenAI LLM pipeline.

    Phase 2A: always matches ``USER_MESSAGE`` — the handler executes
    the existing LLM call logic.  Future phases may add higher-priority
    rules (closing CTA, negotiation reply) that preempt this fallback.
    """

    priority = 90

    def matches(self, trigger: AgentTrigger, context: AgentContext) -> bool:
        return trigger is AgentTrigger.USER_MESSAGE

    async def decide(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        return [
            AgentAction(
                type="call_llm",
                payload={"text": context.text},
            ),
        ]
