"""
core.services.agent.base
~~~~~~~~~~~~~~~~~~~~~~~~~
Agent vocabulary and orchestrator — Phase 1D.

Defines the trigger/context/action types and the top-level
:class:`AgentOrchestrator` which delegates all decisions to
:class:`~core.services.agent.engine.AgentDecisionEngine`.

Import constraints:
  - stdlib only (+ core layer types) at module level
  - Engine import is lazy (inside method body) to avoid circular deps
  - Cooldown import is lazy (inside method body) to avoid early Redis init
  - NO imports from ``apps/``
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from shared.logging import get_logger

log = get_logger(__name__)


# ── Trigger ────────────────────────────────────────────────────────────────


class AgentTrigger(str, Enum):
    """Events that the orchestrator can react to.

    Each value maps to an existing branch in the AI conversation
    pipeline or a sibling handler.
    """

    USER_MESSAGE = "user_message"
    """Free-text message entering the AI pipeline."""

    CATALOG_OPEN = "catalog_open"
    """User asked about the catalog / design options."""

    PRICING_DONE = "pricing_done"
    """Price calculation was shown to the user."""

    INACTIVITY = "inactivity"
    """Follow-up timer fired after a period of silence."""

    OBJECTION = "objection"
    """Price / delay / trust objection detected."""

    ATTEMPT_CLOSE = "attempt_close"
    """Post-LLM-reply close-attempt evaluation (Phase 2B)."""

    FOLLOWUP_DUE = "followup_due"
    """Scheduled follow-up is overdue for a lead (Phase 2C)."""

    PHONE_CAPTURED = "phone_captured"
    """User shared their phone number via FSM or free-text (Phase 2D)."""

    LEAD_CREATED = "lead_created"
    """Lead committed to database with real data (Phase 2E)."""

    STALE_LEAD = "stale_lead"
    """Lead inactive beyond threshold — tiered stale-lead processing (Phase 2F)."""

    ORDER_DROPOFF = "order_dropoff"
    """User abandoned measurement or order FSM mid-flow."""


# ── Context ────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class AgentContext:
    """Snapshot of everything the orchestrator needs to make a decision.

    Every field mirrors data that handlers already load before
    entering the AI pipeline.
    """

    user_id: int
    """Telegram user ID."""

    text: str = ""
    """Current user message (may be empty for non-message triggers)."""

    memory: dict = field(default_factory=dict)
    """Redis AI memory dict from ``_load_ai_memory(user_id)``."""

    score: int = 0
    """Redis lead score (0-100) from ``_get_lead_score(user_id)``."""

    fsm_data: dict = field(default_factory=dict)
    """aiogram FSM data snapshot from ``state.get_data()``."""

    chat_type: str = "private"
    """Telegram chat type: ``"private"``, ``"group"``, ``"supergroup"``."""

    lead_id: int | None = None
    """Database lead ID when resolved, ``None`` otherwise."""

    objection_type: str | None = None
    """Detected objection type (e.g. ``"expensive"``, ``"delay"``)."""

    objection_severity: str | None = None
    """Objection severity: ``"low"``, ``"medium"``, or ``"high"``."""

    intent: str | None = None
    """LLM-detected user intent (e.g. ``"price"``, ``"measurement"``)."""

    closing_confidence: float | None = None
    """AI-assessed closing confidence (0.0-1.0)."""

    follow_up_count: int = 0
    """Number of follow-ups already sent for this lead."""

    lead_temperature: str | None = None
    """Lead temperature: ``"hot"``, ``"warm"``, ``"cold"``."""

    last_activity_ts: int | None = None
    """Unix timestamp of last user activity (from Redis)."""


# ── Action ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentAction:
    """A single instruction the orchestrator returns to the handler.

    The handler is responsible for executing the action; the
    orchestrator only *decides* what should happen.
    """

    type: str
    """Action identifier (e.g. ``"reply"``, ``"set_state"``)."""

    payload: dict = field(default_factory=dict)
    """Action-specific data (text, keyboard config, target state, …)."""


# ── Orchestrator ───────────────────────────────────────────────────────────


# ── Per-trigger cooldown defaults ──────────────────────────────────────────
# Maps each trigger to (ActionType-value, cooldown-in-seconds).
# Rationale for each default:
#   USER_MESSAGE / OBJECTION  — 5s: prevent rapid-fire spam; user can still
#                                converse at normal pace.
#   ATTEMPT_CLOSE             — 120s: closing CTAs are intrusive; 2-min gap.
#   CATALOG_OPEN              — 30s: catalog is user-initiated, light gate.
#   PHONE_CAPTURED / LEAD_CREATED — 60s: milestone events, unlikely to
#                                   repeat within a minute legitimately.
#   FOLLOWUP_DUE / INACTIVITY / STALE_LEAD — 300s: scheduled background
#                                            triggers; 5-min gate prevents
#                                            scheduler pile-ups.
#   ORDER_DROPOFF             — 60s: one dropoff notice per minute is enough.
#   PRICING_DONE              — 10s: light gate, user-initiated.
_TRIGGER_COOLDOWNS: dict[str, tuple[str, int]] = {
    AgentTrigger.USER_MESSAGE.value:  ("reply", 5),
    AgentTrigger.OBJECTION.value:     ("reply", 5),
    AgentTrigger.ATTEMPT_CLOSE.value: ("attempt_close", 120),
    AgentTrigger.CATALOG_OPEN.value:  ("catalog_followup", 30),
    AgentTrigger.PHONE_CAPTURED.value: ("admin_alert", 60),
    AgentTrigger.LEAD_CREATED.value:  ("admin_alert", 60),
    AgentTrigger.FOLLOWUP_DUE.value:  ("schedule_followup", 300),
    AgentTrigger.INACTIVITY.value:    ("reply", 300),
    AgentTrigger.STALE_LEAD.value:    ("reply", 300),
    AgentTrigger.ORDER_DROPOFF.value: ("reply", 60),
    AgentTrigger.PRICING_DONE.value:  ("reply", 10),
}


class AgentOrchestrator:
    """Top-level agent entry point — Phase 1D.

    Delegates all decisions to the rule-chain
    :class:`~core.services.agent.engine.AgentDecisionEngine`.
    The engine and cooldown manager are lazily imported and cached
    to avoid circular deps at module load time.
    """

    def __init__(self) -> None:
        self._engine: object | None = None
        self._cooldown: object | None = None

    def _get_cooldown(self) -> object:
        """Lazily instantiate the cooldown manager."""
        if self._cooldown is None:
            from core.services.agent.cooldown import AgentCooldownManager

            self._cooldown = AgentCooldownManager()
        return self._cooldown

    async def process(
        self,
        trigger: AgentTrigger,
        context: AgentContext,
    ) -> list[AgentAction]:
        """Decide what actions to take for *trigger* + *context*.

        Checks per-trigger cooldown before evaluating rules.
        Returns an empty list when cooldown is active or no rule matches.

        ADR — Cooldown semantics (Phase 1A, 2026-04-02)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        This is an **action** cooldown, not an evaluation cooldown.
        ``mark_acted()`` fires only when the engine returns non-empty
        actions (i.e. the orchestrator actually decided to *do* something).
        No-op evaluations (engine returns ``[]``) do NOT consume the
        cooldown window, so a subsequent trigger can still fire normally.

        Rationale: we want to prevent rapid-fire side-effects (messages
        sent, DB writes, admin alerts) while still letting the system
        check whether it *should* act.  If evaluation-level throttling
        becomes necessary (e.g. to limit OpenAI spend even on no-op
        evaluations), add a separate ``eval_cooldown`` gate before the
        ``_engine.evaluate()`` call.
        """
        # ── Per-trigger rate limiting ─────────────────────────────────
        cooldown_spec = _TRIGGER_COOLDOWNS.get(trigger.value)
        if cooldown_spec is not None:
            action_type_value, cooldown_seconds = cooldown_spec
            try:
                from core.services.agent.cooldown import ActionType

                cd = self._get_cooldown()
                at = ActionType(action_type_value)
                if not await cd.can_act(  # type: ignore[union-attr]
                    context.user_id, at, cooldown_seconds=cooldown_seconds,
                ):
                    log.debug(
                        "agent_cooldown_blocked",
                        trigger=trigger.value,
                        user_id=context.user_id,
                        action=action_type_value,
                        cooldown_s=cooldown_seconds,
                    )
                    return []
            except Exception:
                # Fail-open: if cooldown check fails, proceed to evaluation
                log.warning(
                    "agent_cooldown_check_error",
                    trigger=trigger.value,
                    user_id=context.user_id,
                    exc_info=True,
                )

        # ── Rule evaluation ───────────────────────────────────────────
        if self._engine is None:
            from core.services.agent.engine import AgentDecisionEngine

            self._engine = AgentDecisionEngine()
        actions = await self._engine.evaluate(trigger, context)  # type: ignore[union-attr]

        # ── Mark cooldown after successful evaluation ─────────────────
        if actions and cooldown_spec is not None:
            try:
                from core.services.agent.cooldown import ActionType

                cd = self._get_cooldown()
                at = ActionType(cooldown_spec[0])
                await cd.mark_acted(  # type: ignore[union-attr]
                    context.user_id, at, cooldown_seconds=cooldown_spec[1],
                )
            except Exception:
                log.warning(
                    "agent_cooldown_mark_error",
                    trigger=trigger.value,
                    user_id=context.user_id,
                    exc_info=True,
                )

        return actions
