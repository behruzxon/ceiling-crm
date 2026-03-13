"""Closing readiness jobs — opportunity alerts and close-loss risk detection."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_closing_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register closing readiness scanner."""
    scheduler.add_job(
        run_closing_scanner,
        trigger="interval",
        minutes=10,
        id="run_closing_scanner",
        replace_existing=True,
    )


async def run_closing_scanner() -> None:
    """Scan active leads for closing opportunities and close-loss risks.

    Sends deduped alerts to admin group:
    - Closing opportunity: READY_TO_CLOSE leads (2h dedup) — business hours only
    - Close-loss risk: critical alerts allowed anytime

    Normal alerts are suppressed during off-hours.
    """
    from datetime import datetime, timezone

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys, CacheTTL
    from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
    from infrastructure.database.session import get_session_factory
    from shared.config import get_settings
    from shared.utils.business_hours import is_off_hours
    from shared.utils.telegram_send import safe_send_message

    settings = get_settings()
    admin_group_id = settings.bot.admin_group_id
    bot_token = settings.bot.token.get_secret_value()

    if not admin_group_id:
        return

    off_hours = is_off_hours()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    factory = get_session_factory()
    bot: Bot | None = None
    alerts_sent = 0

    try:
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            leads = await repo.get_active_leads(limit=40)

        if not leads:
            return

        redis = get_redis()

        from core.services.closing_readiness_service import (
            TIER_READY_TO_CLOSE,
            build_close_loss_risk_alert,
            build_closing_opportunity_alert,
            detect_close_loss_risk,
            evaluate_closing_readiness,
            select_closing_tactic,
        )

        from core.services.signal_vector_service import build_signal_vector

        for lead in leads:
            if alerts_sent >= 6:
                break

            signals = await _build_lead_signals(lead, now_ts)

            # Build SignalVector for no-double-counting scoring
            sv = build_signal_vector(
                lead_score=signals.get("score", 0),
                health_score=signals.get("health_score", 50),
                closing_confidence=signals.get("closing_confidence"),
                phone_captured=signals.get("phone_captured", False),
                has_area=signals.get("area_m2") is not None,
                area_m2=signals.get("area_m2"),
                has_district=signals.get("has_district", False),
                closing_attempted=signals.get("closing_attempted", False),
                last_objection=signals.get("last_objection"),
                last_objection_severity=signals.get("last_objection_severity"),
                objection_resolved=signals.get("objection_resolved", False),
                follow_up_count=signals.get("follow_up_count", 0),
                lead_temperature=signals.get("lead_temperature"),
                buyer_type=signals.get("buyer_type"),
                current_stage=signals.get("current_stage"),
                minutes_since_last_activity=signals.get(
                    "minutes_since_last_activity", 0
                ),
                deal_probability_percent=signals.get("deal_probability_percent"),
            )

            # Run closing readiness
            readiness = evaluate_closing_readiness(signal_vector=sv)

            # ── 1. Closing opportunity (READY_TO_CLOSE only) ──────────
            # Normal alert — business hours only
            if readiness.readiness_tier == TIER_READY_TO_CLOSE and not off_hours:
                dedup_key = CacheKeys.closing_opportunity(lead.id)
                was_set = await redis.set(
                    dedup_key, "1",
                    ttl=CacheTTL.CLOSING_OPPORTUNITY,
                    nx=True,
                )
                if was_set:
                    tactic = select_closing_tactic(
                        readiness_tier=readiness.readiness_tier,
                        closing_score=readiness.closing_score,
                        last_objection=signals.get("last_objection"),
                        objection_resolved=signals.get("objection_resolved", False),
                        buyer_type=signals.get("buyer_type"),
                        phone_captured=signals.get("phone_captured", False),
                        area_m2=signals.get("area_m2"),
                        closing_attempted=signals.get("closing_attempted", False),
                        minutes_since_last_activity=signals.get(
                            "minutes_since_last_activity", 0
                        ),
                        follow_up_count=signals.get("follow_up_count", 0),
                        lead_temperature=signals.get("lead_temperature"),
                    )
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    alert = build_closing_opportunity_alert(
                        lead_id=lead.id,
                        lead_name=lead.name or "?",
                        lead_phone=lead.phone or "\u2014",
                        closing_score=readiness.closing_score,
                        tactic_uz=tactic.tactic_uz,
                        suggested_message_uz=tactic.suggested_message_uz,
                        timeline_hours=readiness.suggested_timeline_hours,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

            # ── 2. Close-loss risk detection ──────────────────────────
            risk = detect_close_loss_risk(
                readiness_tier=readiness.readiness_tier,
                closing_score=readiness.closing_score,
                minutes_since_last_activity=signals.get(
                    "minutes_since_last_activity", 0
                ),
                health_score=signals.get("health_score", 50),
                lead_temperature=signals.get("lead_temperature"),
                last_objection=signals.get("last_objection"),
                objection_resolved=signals.get("objection_resolved", False),
            )

            if risk.detected:
                dedup_key = CacheKeys.closing_loss_risk(lead.id)
                was_set = await redis.set(
                    dedup_key, "1",
                    ttl=CacheTTL.CLOSING_LOSS_RISK,
                    nx=True,
                )
                if was_set:
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    alert = build_close_loss_risk_alert(
                        lead_id=lead.id,
                        lead_name=lead.name or "?",
                        lead_phone=lead.phone or "\u2014",
                        minutes_waiting=risk.minutes_waiting,
                        risk_reason_uz=risk.risk_reason_uz,
                        recommended_action_uz=risk.recommended_action_uz,
                        risk_level=risk.risk_level,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

    except Exception:
        log.exception("closing_scanner_error")
    finally:
        if bot:
            await bot.session.close()

    if alerts_sent:
        log.info("closing_scanner_alerts", count=alerts_sent)


# ── Helpers ────────────────────────────────────────────────────────────────


async def _build_lead_signals(lead: object, now_ts: int) -> dict:
    """Build signal dict for closing readiness from a lead + Redis memory."""
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

    # Inactivity
    last_ts = mem.get("last_activity_ts") or mem.get("updated_at")
    if last_ts:
        mins_inactive = max(0, (now_ts - int(last_ts)) // 60)
    else:
        from datetime import datetime, timezone
        mins_inactive = int(
            (datetime.now(timezone.utc) - lead.updated_at).total_seconds() / 60
        )

    # Health score
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
    }


def _classify_temp(score: int) -> str:
    if score >= 60:
        return "hot"
    if score >= 30:
        return "warm"
    return "cold"
