"""
apps.bot.handlers.admin.radar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/radar — Deal Radar: shows top leads ranked by urgency and business value.

Loads active leads from DB, runs the full intelligence stack per lead,
ranks them with ``deal_radar_service``, and shows the top 5 in a concise
admin card.

Access: ADMIN / SUPERADMIN roles.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:radar")

_MGMT_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)


@router.message(Command("radar"), RoleFilter(*_MGMT_ROLES))
async def cmd_radar(message: Message, **data: object) -> None:
    """Show top 5 leads ranked by urgency and business value."""
    await message.answer("\U0001f4e1 Radar tahlil qilinmoqda...")

    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session)
            leads = await repo.get_active_leads(limit=30)

        if not leads:
            await message.answer("\U0001f4e1 Faol lidlar topilmadi.")
            return

        # Build signal dicts for each lead
        lead_signals = await _build_signals_batch(leads)

        # Rank
        from core.services.deal_radar_service import (
            BUCKET_LABELS,
            rank_leads_for_radar,
        )

        ranked = rank_leads_for_radar(lead_signals, top_n=5)

        if not ranked:
            await message.answer("\U0001f4e1 Hech qanday lid topilmadi.")
            return

        # Build response card
        lines: list[str] = ["\U0001f4e1 <b>Deal Radar — Top 5</b>\n"]
        lead_map = {lead.id: lead for lead in leads}

        for i, r in enumerate(ranked, 1):
            lead = lead_map.get(r["lead_id"])
            name = lead.name if lead else "?"
            phone = lead.phone if lead and lead.phone else "\u2014"
            district = lead.district if lead and lead.district else "\u2014"

            bucket_label = BUCKET_LABELS.get(r["radar_bucket"], r["radar_bucket"])

            lines.append(
                f"<b>{i}. {name}</b> #{r['lead_id']}\n"
                f"   {bucket_label} | \U0001f3af {r['radar_priority_score']}%\n"
                f"   \U0001f4f1 {phone} | \U0001f4cd {district}\n"
                f"   \U0001f4a1 {r['radar_reason']}\n"
                f"   \u27a1 <i>{r['recommended_immediate_action']}</i>\n"
            )

        lines.append("\n/lead_ID \u2014 batafsil ko'rish")
        await message.answer("\n".join(lines))

    except Exception:
        log.exception("radar_command_failed")
        await message.answer("\u274c Radar xatolik yuz berdi.")


async def _build_signals_batch(leads: list) -> list[dict]:
    """Build signal dicts for a batch of leads by running the intelligence stack."""
    from apps.bot.handlers.private.ai_memory import _load_ai_memory

    results: list[dict] = []
    for lead in leads:
        try:
            signals = await _build_signals_for_lead(lead)
            results.append(signals)
        except Exception:
            log.warning("radar_signal_build_failed", lead_id=lead.id)
            # Fallback: minimal signals from DB fields only
            results.append({
                "lead_id": lead.id,
                "score": lead.score or 0,
                "phone_captured": bool(lead.phone),
                "has_area": lead.room_area is not None,
                "has_district": bool(lead.district),
                "lead_status": lead.lead_status,
                "lead_temperature": lead.lead_temperature,
                "closing_confidence": lead.closing_confidence,
                "follow_up_count": lead.follow_up_count or 0,
            })
    return results


async def _build_signals_for_lead(lead: object) -> dict:
    """Build a complete signal dict for a single lead."""
    from apps.bot.handlers.private.ai_memory import _load_ai_memory

    mem: dict = {}
    try:
        mem = await _load_ai_memory(lead.user_id)
    except Exception:
        pass

    # Use Redis score if available, else DB score
    ai_score = lead.score or 0
    try:
        from apps.bot.handlers.private.ai_scoring import _get_lead_score
        redis_score = await _get_lead_score(lead.user_id)
        if redis_score > ai_score:
            ai_score = redis_score
    except Exception:
        pass

    # ── Build SignalVector ──────────────────────────────────────────
    sv = None
    try:
        from core.services.signal_vector_service import (
            build_signal_vector,
            with_deal_probability,
        )
        sv = build_signal_vector(
            lead_score=ai_score,
            closing_confidence=lead.closing_confidence,
            phone_captured=bool(lead.phone),
            has_area=lead.room_area is not None,
            area_m2=float(lead.room_area) if lead.room_area else None,
            has_district=bool(lead.district),
            closing_attempted=bool(mem.get("last_closing_attempt")),
            last_objection=mem.get("last_objection"),
            follow_up_count=lead.follow_up_count or 0,
            lead_temperature=lead.lead_temperature,
            buyer_type=mem.get("buyer_type"),
            lead_status=lead.lead_status,
            last_activity_ts=mem.get("updated_at"),
        )
    except Exception:
        pass

    # ── Deal probability ──────────────────────────────────────────────
    dp_pct: int | None = None
    try:
        from shared.utils.deal_probability import evaluate_deal_probability
        dp = evaluate_deal_probability(signal_vector=sv) if sv else \
            evaluate_deal_probability(
                score=ai_score,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district),
                follow_up_count=lead.follow_up_count or 0,
            )
        dp_pct = dp.deal_probability_percent
        # Update SV with dp result
        if sv:
            sv = with_deal_probability(sv, dp_pct)
    except Exception:
        pass

    # ── Buyer type ────────────────────────────────────────────────────
    buyer_type: str | None = mem.get("buyer_type")
    if not buyer_type:
        try:
            from core.services.lead_intelligence_service import analyze_buyer_type
            bp = analyze_buyer_type(
                score=ai_score,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                has_district=bool(lead.district),
                deal_probability_percent=dp_pct,
            )
            buyer_type = bp.buyer_type
        except Exception:
            pass

    # ── Revenue ───────────────────────────────────────────────────────
    rev_best: int | None = None
    rev_max: int | None = None
    try:
        from core.services.revenue_predictor_service import predict_lead_revenue
        rev = predict_lead_revenue(
            area_m2=float(lead.room_area) if lead.room_area else None,
            design_type=mem.get("design_type"),
            buyer_type=buyer_type,
            last_objection=mem.get("last_objection"),
            deal_probability_percent=dp_pct,
        )
        rev_best = rev.predicted_revenue_best
        rev_max = rev.predicted_revenue_max
    except Exception:
        pass

    # ── Conversation graph ────────────────────────────────────────────
    decision_stage: str | None = None
    engagement_trend: str | None = None
    try:
        from core.services.conversation_memory_graph_service import analyze_conversation_graph
        cg = analyze_conversation_graph(
            score=ai_score,
            phone_captured=bool(lead.phone),
            has_area=lead.room_area is not None,
            has_district=bool(lead.district),
            deal_probability_percent=dp_pct,
            buyer_type=buyer_type,
            closing_confidence=lead.closing_confidence,
            follow_up_count=lead.follow_up_count or 0,
            last_activity_ts=mem.get("updated_at"),
            memory_created_at=mem.get("created_at"),
            negotiation_tactic=mem.get("last_negotiation_tactic"),
            negotiation_escalated=bool(mem.get("negotiation_escalated")),
            last_objection=mem.get("last_objection"),
        )
        decision_stage = cg.current_decision_stage
        engagement_trend = cg.engagement_trend
    except Exception:
        pass

    # ── Follow-up brain ───────────────────────────────────────────────
    fu_should = True
    fu_type: str | None = None
    try:
        from core.services.followup_brain_service import decide_follow_up
        fd = decide_follow_up(
            score=ai_score,
            deal_probability_percent=dp_pct,
            buyer_type=buyer_type,
            decision_stage=decision_stage,
            engagement_trend=engagement_trend,
            phone_captured=bool(lead.phone),
            has_area=lead.room_area is not None,
            has_district=bool(lead.district),
            follow_up_count=lead.follow_up_count or 0,
            closing_confidence=lead.closing_confidence,
            lead_temperature=lead.lead_temperature,
            last_objection=mem.get("last_objection"),
        )
        fu_should = fd.should_follow_up
        fu_type = fd.follow_up_type
    except Exception:
        pass

    # Enrich SV with upstream results for radar
    sv_for_radar = None
    if sv:
        try:
            from dataclasses import replace as _dc_replace
            sv_for_radar = _dc_replace(
                sv,
                predicted_revenue_best=rev_best,
                predicted_revenue_max=rev_max,
                decision_stage=decision_stage,
                engagement_trend=engagement_trend,
                follow_up_should=fu_should,
                follow_up_type=fu_type if fu_should else None,
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
            )
        except Exception:
            pass

    result = {
        "lead_id": lead.id,
        "score": ai_score,
        "deal_probability_percent": dp_pct,
        "predicted_revenue_best": rev_best,
        "predicted_revenue_max": rev_max,
        "buyer_type": buyer_type,
        "negotiation_escalated": bool(mem.get("negotiation_escalated")),
        "decision_stage": decision_stage,
        "engagement_trend": engagement_trend,
        "follow_up_should": fu_should,
        "follow_up_type": fu_type,
        "phone_captured": bool(lead.phone),
        "has_area": lead.room_area is not None,
        "has_district": bool(lead.district),
        "closing_attempted": bool(mem.get("last_closing_attempt")),
        "closing_confidence": lead.closing_confidence,
        "lead_temperature": lead.lead_temperature,
        "lead_status": lead.lead_status,
        "follow_up_count": lead.follow_up_count or 0,
        "last_activity_ts": mem.get("updated_at"),
    }
    if sv_for_radar:
        result["signal_vector"] = sv_for_radar
    return result
