"""
apps.bot.handlers.private.ai_notifications
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin notification helpers and AI scoring persistence.

Orchestrates deal probability, buyer type, revenue, conversation graph,
and follow-up brain for the admin lead card.
"""
from __future__ import annotations

from typing import Any

from infrastructure.di import get_lead_notification_service
from shared.logging import get_logger

log = get_logger(__name__)


# ── AI scoring -> lead persistence (non-fatal, fire-and-forget) ─────────────

async def _update_lead_ai_scoring(
    *,
    user_id: int,
    lead_temperature: str | None,
    closing_confidence: float | None,
) -> None:
    """Find the latest lead for *user_id* and persist AI scoring. Never raises."""
    from core.services.lead_scoring_service import LeadScoringService

    await LeadScoringService().rescore_lead(
        user_id=user_id,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
        trigger="ai_message",
    )


# ── Phone capture helper ────────────────────────────────────────────────────

async def _notify_phone_captured(
    *,
    phone: str,
    profile: dict[str, Any],
    from_user: Any,
    chat_type: str,
    chat_id: int,
) -> None:
    """Fire-and-forget admin alert when a phone is detected in free text."""
    try:
        name = profile.get("name") or (from_user.first_name if from_user else None)
        username = from_user.username if from_user else None
        user_id = from_user.id if from_user else None
        svc = get_lead_notification_service()
        await svc.notify_draft_lead(
            phone=phone,
            name=name,
            username=username,
            user_id=user_id,
            chat_type=chat_type,
            chat_id=chat_id,
        )
    except Exception:
        log.warning("phone_capture_notify_failed", phone=phone)


# ── AI lead collected (full intelligence stack) ─────────────────────────────

async def _notify_ai_lead_collected(
    *,
    phone: str,
    district: str,
    area: float | None,
    room: str | None,
    design: str | None = None,
    name: str | None,
    from_user: Any,
    score: int = 0,
    last_message: str = "",
    lead_id: int | None = None,
    last_objection: str | None = None,
    closing_attempted: bool = False,
    closing_action: str | None = None,
    intent: str | None = None,
    follow_up_count: int = 0,
    closing_confidence: float | None = None,
    negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    last_activity_ts: int | None = None,
    memory_created_at: int | None = None,
) -> None:
    """Fire-and-forget admin notification for AI-collected lead. Never raises."""
    try:
        from core.services.ai_orchestrator_service import build_ai_orchestrator_state

        orch = build_ai_orchestrator_state(
            name=name,
            district=district,
            phone=phone,
            score=score,
            closing_confidence=closing_confidence,
            phone_captured=bool(phone),
            has_area=area is not None,
            area_m2=area,
            has_district=bool(district),
            closing_attempted=closing_attempted,
            closing_action=closing_action,
            last_objection=last_objection,
            intent=intent,
            follow_up_count=follow_up_count,
            design_type=design,
            negotiation_tactic=negotiation_tactic,
            negotiation_escalated=negotiation_escalated,
            last_activity_ts=last_activity_ts,
            memory_created_at=memory_created_at,
        )
        brain = orch.sales_brain

        svc = get_lead_notification_service()
        await svc.notify_ai_lead_collected(
            phone=phone,
            district=district,
            area=area,
            room=room,
            design=design,
            name=name,
            username=from_user.username if from_user else None,
            user_id=from_user.id if from_user else None,
            score=score,
            last_message=last_message,
            lead_id=lead_id,
            last_objection=last_objection,
            closing_attempted=closing_attempted,
            closing_action=closing_action,
            deal_probability=brain.deal_probability,
            buyer_profile=brain.buyer_profile,
            revenue_estimate=brain.revenue_estimate,
            negotiation_tactic=(
                brain.negotiation_result.tactic  # type: ignore[union-attr]
                if brain.negotiation_result
                and brain.negotiation_result.negotiation_detected  # type: ignore[union-attr]
                else negotiation_tactic
            ),
            negotiation_escalated=negotiation_escalated,
            conversation_graph=brain.conversation_graph,
            followup_decision=brain.followup_decision,
            sales_brain=brain,
        )
    except Exception:
        log.warning("notify_ai_lead_collected_failed", phone=phone)


# ── Warm interest notification ──────────────────────────────────────────────

async def _notify_warm_interest(
    *,
    topic: str,
    from_user: Any,
    name: str | None = None,
) -> None:
    """Fire-and-forget WARM lead interest notification. Never raises."""
    try:
        svc = get_lead_notification_service()
        await svc.notify_lead_interest(
            score="warm",
            name=name,
            username=from_user.username if from_user else None,
            user_id=from_user.id if from_user else None,
            topic=topic,
        )
    except Exception:
        log.warning("notify_warm_interest_failed", topic=topic)
