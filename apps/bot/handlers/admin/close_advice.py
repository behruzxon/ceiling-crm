"""
apps.bot.handlers.admin.close_advice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/close_advice <lead_id> — AI Closer: shows closing readiness score,
recommended tactic, copyable message, and risk assessment.

Access: ADMIN / SUPERADMIN roles.
"""
from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:close_advice")

_MGMT_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)


@router.message(Command("close_advice"), RoleFilter(*_MGMT_ROLES))
async def cmd_close_advice(message: Message, **data: object) -> None:
    """Show close advice for a specific lead."""
    # Parse lead_id from command args
    lead_id: int | None = None
    if message.text:
        parts = message.text.split()
        if len(parts) >= 2:
            try:
                lead_id = int(parts[1])
            except ValueError:
                pass

    if lead_id is None:
        await message.answer(
            "\u2753 Foydalanish: /close_advice &lt;lead_id&gt;\n"
            "Masalan: /close_advice 145"
        )
        return

    await message.answer("\U0001f3af Tahlil qilinmoqda...")

    try:
        # Load lead from DB
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session)
            lead = await repo.get_by_id(lead_id)

        if not lead:
            await message.answer(f"\u274c Lead #{lead_id} topilmadi.")
            return

        # Build signals and run closing readiness engine
        signals = await _build_closing_signals(lead)

        from core.services.closing_readiness_service import (
            build_close_advice_card,
            detect_close_loss_risk,
            evaluate_closing_readiness,
            select_closing_tactic,
        )

        sv = signals.pop("_signal_vector", None)
        readiness = evaluate_closing_readiness(signal_vector=sv) if sv else \
            evaluate_closing_readiness(**signals)

        tactic = select_closing_tactic(
            readiness_tier=readiness.readiness_tier,
            closing_score=readiness.closing_score,
            last_objection=signals.get("last_objection"),
            objection_resolved=signals.get("objection_resolved", False),
            buyer_type=signals.get("buyer_type"),
            phone_captured=signals.get("phone_captured", False),
            area_m2=signals.get("area_m2"),
            closing_attempted=signals.get("closing_attempted", False),
            minutes_since_last_activity=signals.get("minutes_since_last_activity", 0),
            follow_up_count=signals.get("follow_up_count", 0),
            lead_temperature=signals.get("lead_temperature"),
        )

        # Build main advice card
        card = build_close_advice_card(
            lead_id=lead.id,
            lead_name=lead.name or "?",
            lead_phone=lead.phone or "\u2014",
            readiness=readiness,
            tactic=tactic,
        )

        # Check close-loss risk
        risk = detect_close_loss_risk(
            readiness_tier=readiness.readiness_tier,
            closing_score=readiness.closing_score,
            minutes_since_last_activity=signals.get("minutes_since_last_activity", 0),
            health_score=signals.get("health_score", 50),
            lead_temperature=signals.get("lead_temperature"),
            last_objection=signals.get("last_objection"),
            objection_resolved=signals.get("objection_resolved", False),
        )

        if risk.detected:
            _risk_badges = {"warning": "\U0001f7e1", "critical": "\U0001f534"}
            badge = _risk_badges.get(risk.risk_level, "\u26aa")
            card += (
                f"\n\n{badge} <b>Yo'qotish xavfi:</b> {risk.risk_reason_uz}\n"
                f"\u27a1 {risk.recommended_action_uz}"
            )

        # Send (split if needed)
        if len(card) <= 4096:
            await message.answer(card)
        else:
            parts = card.split("\n\n")
            chunk = ""
            for part in parts:
                if len(chunk) + len(part) + 2 > 4000:
                    await message.answer(chunk)
                    chunk = part
                else:
                    chunk = f"{chunk}\n\n{part}" if chunk else part
            if chunk:
                await message.answer(chunk)

    except Exception:
        log.exception("close_advice_command_failed")
        await message.answer("\u274c Close advice xatolik yuz berdi.")


async def _build_closing_signals(lead: object) -> dict:
    """Build signal dict for closing readiness evaluation."""
    mem: dict = {}
    try:
        from apps.bot.handlers.private.ai_memory import _load_ai_memory
        mem = await _load_ai_memory(lead.user_id) or {}
    except Exception:
        pass

    # Redis score
    ai_score = lead.score or 0
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys
        raw = await get_redis().get(CacheKeys.ai_lead_score(lead.user_id))
        if raw:
            ai_score = max(ai_score, int(raw))
    except Exception:
        pass

    # Minutes since last activity
    now_ts = int(datetime.now(UTC).timestamp())
    last_ts = mem.get("last_activity_ts") or mem.get("updated_at")
    if last_ts:
        mins_inactive = max(0, (now_ts - int(last_ts)) // 60)
    else:
        mins_inactive = int(
            (datetime.now(UTC) - lead.updated_at).total_seconds() / 60
        )

    # Health score via conversation intelligence
    health_score = 50
    try:
        from core.services.conversation_intelligence_service import (
            analyze_conversation,
        )
        stage_str = (
            lead.current_stage.value
            if hasattr(lead.current_stage, "value")
            else str(lead.current_stage)
        )
        ci = analyze_conversation(
            score=ai_score,
            last_objection=mem.get("last_objection"),
            phone_captured=bool(lead.phone),
            area_m2=float(lead.room_area) if lead.room_area else None,
            minutes_since_last_activity=mins_inactive,
            follow_up_count=lead.follow_up_count or 0,
            lead_temperature=lead.lead_temperature,
            closing_confidence=lead.closing_confidence,
            buyer_type=mem.get("buyer_type"),
            last_negotiation_tactic=mem.get("last_negotiation_tactic"),
            has_district=bool(lead.district),
            current_stage=stage_str,
        )
        health_score = ci.health_score
    except Exception:
        pass

    # Deal probability
    dp_pct: int | None = None
    try:
        from shared.utils.deal_probability import evaluate_deal_probability
        dp = evaluate_deal_probability(
            score=ai_score,
            closing_confidence=lead.closing_confidence,
            phone_captured=bool(lead.phone),
            has_area=lead.room_area is not None,
            area_m2=float(lead.room_area) if lead.room_area else None,
            has_district=bool(lead.district),
            follow_up_count=lead.follow_up_count or 0,
        )
        dp_pct = dp.deal_probability_percent
    except Exception:
        pass

    # Buyer type
    buyer_type = mem.get("buyer_type")
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

    stage_str = (
        lead.current_stage.value
        if hasattr(lead.current_stage, "value")
        else str(lead.current_stage)
    )

    objection_resolved = bool(
        mem.get("last_objection") and mem.get("last_negotiation_tactic")
    )

    # Build SignalVector for closing_readiness
    _sv = None
    try:
        from core.services.signal_vector_service import (
            build_signal_vector,
            with_deal_probability,
        )
        _sv = build_signal_vector(
            lead_score=ai_score,
            health_score=health_score,
            closing_confidence=lead.closing_confidence,
            phone_captured=bool(lead.phone),
            has_area=lead.room_area is not None,
            area_m2=float(lead.room_area) if lead.room_area else None,
            has_district=bool(lead.district),
            closing_attempted=bool(mem.get("last_closing_attempt")),
            objection_resolved=objection_resolved,
            last_objection=mem.get("last_objection"),
            last_objection_severity=mem.get("last_objection_severity"),
            follow_up_count=lead.follow_up_count or 0,
            lead_temperature=lead.lead_temperature,
            buyer_type=buyer_type,
            current_stage=stage_str,
            minutes_since_last_activity=mins_inactive,
        )
        if dp_pct is not None:
            _sv = with_deal_probability(_sv, dp_pct)
    except Exception:
        pass

    return {
        "score": ai_score,
        "health_score": health_score,
        "last_objection": mem.get("last_objection"),
        "last_objection_severity": mem.get("last_objection_severity"),
        "objection_resolved": objection_resolved,
        "minutes_since_last_activity": mins_inactive,
        "current_stage": stage_str,
        "phone_captured": bool(lead.phone),
        "area_m2": float(lead.room_area) if lead.room_area else None,
        "has_district": bool(lead.district),
        "follow_up_count": lead.follow_up_count or 0,
        "closing_confidence": lead.closing_confidence,
        "lead_temperature": lead.lead_temperature,
        "buyer_type": buyer_type,
        "closing_attempted": bool(mem.get("last_closing_attempt")),
        "deal_probability_percent": dp_pct,
        "_signal_vector": _sv,
    }
