"""Sales autopilot jobs — opportunity detection, risk alerts, NBA suggestions."""

from __future__ import annotations

from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_sales_autopilot_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all sales autopilot jobs."""
    # Full autopilot scan every 10 min
    scheduler.add_job(
        run_sales_autopilot,
        trigger="interval",
        minutes=10,
        id="run_sales_autopilot",
        replace_existing=True,
    )


async def run_sales_autopilot() -> None:
    """Analyze active leads: detect opportunities, risks, suggest actions.

    Covers Phase 13: NBA engine, opportunity detection, lost lead
    prevention, closing suggestions, pipeline insights.

    Normal alerts (opportunity, closing) are suppressed during off-hours.
    At-risk alerts with urgency=critical are sent anytime.
    """
    from datetime import datetime

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
    now_ts = int(datetime.now(UTC).timestamp())

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

        from core.services.conversation_intelligence_service import (
            analyze_conversation,
        )
        from core.services.next_best_action_service import (
            CLOSING_TACTIC_LABELS,
            build_at_risk_alert_text,
            build_closing_alert_text,
            build_opportunity_alert_text,
            detect_at_risk,
            detect_opportunity,
            suggest_closing_tactic,
        )

        for lead in leads:
            if alerts_sent >= 6:
                break

            mem = await _load_lead_memory(lead.user_id)
            score = await _get_lead_score(lead.user_id)

            # Compute inactivity
            last_ts = mem.get("last_activity_ts") or mem.get("updated_at")
            if last_ts:
                mins_inactive = max(0, (now_ts - int(last_ts)) // 60)
            else:
                mins_inactive = int((datetime.now(UTC) - lead.updated_at).total_seconds() / 60)

            stage_str = (
                lead.current_stage.value
                if hasattr(lead.current_stage, "value")
                else str(lead.current_stage)
            )
            temp = lead.lead_temperature or _classify_temp(score)

            # Run conversation intelligence for health score
            ci = analyze_conversation(
                score=score,
                last_objection=mem.get("last_objection"),
                last_objection_severity=mem.get("last_objection_severity"),
                phone_captured=bool(lead.phone),
                area_m2=float(lead.room_area) if lead.room_area else None,
                minutes_since_last_activity=mins_inactive,
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=temp,
                closing_confidence=lead.closing_confidence,
                buyer_type=mem.get("buyer_type"),
                last_negotiation_tactic=mem.get("last_negotiation_tactic"),
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
                has_district=bool(lead.district),
                last_closing_attempt=mem.get("last_closing_attempt"),
                lead_status=lead.lead_status,
                current_stage=stage_str,
            )

            objection_resolved = bool(
                mem.get("last_objection") and mem.get("last_negotiation_tactic")
            )

            # Build SignalVector
            sv = None
            try:
                from core.services.signal_vector_service import (
                    build_signal_vector,
                    with_deal_probability,
                )

                sv = build_signal_vector(
                    lead_score=score,
                    health_score=ci.health_score,
                    closing_confidence=lead.closing_confidence,
                    phone_captured=bool(lead.phone),
                    has_area=lead.room_area is not None,
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    has_district=bool(lead.district),
                    closing_attempted=bool(mem.get("last_closing_attempt")),
                    objection_resolved=objection_resolved,
                    last_objection=mem.get("last_objection"),
                    follow_up_count=lead.follow_up_count or 0,
                    lead_temperature=temp,
                    buyer_type=mem.get("buyer_type"),
                    current_stage=stage_str,
                    minutes_since_last_activity=mins_inactive,
                    lead_status=lead.lead_status,
                )
            except Exception:
                pass

            # Get deal probability
            dp_pct: int | None = None
            try:
                from shared.utils.deal_probability import evaluate_deal_probability

                dp = (
                    evaluate_deal_probability(signal_vector=sv)
                    if sv
                    else evaluate_deal_probability(
                        score=score,
                        closing_confidence=lead.closing_confidence,
                        phone_captured=bool(lead.phone),
                        has_area=lead.room_area is not None,
                        area_m2=float(lead.room_area) if lead.room_area else None,
                        has_district=bool(lead.district),
                        follow_up_count=lead.follow_up_count or 0,
                    )
                )
                dp_pct = dp.deal_probability_percent
                if sv:
                    sv = with_deal_probability(sv, dp_pct)
            except Exception:
                pass

            # ── 1. Opportunity detection ───────────────────────────
            opp = (
                detect_opportunity(signal_vector=sv)
                if sv
                else detect_opportunity(
                    score=score,
                    health_score=ci.health_score,
                    last_objection=mem.get("last_objection"),
                    objection_resolved=objection_resolved,
                    minutes_since_last_activity=mins_inactive,
                    phone_captured=bool(lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    closing_confidence=lead.closing_confidence,
                    deal_probability_percent=dp_pct,
                )
            )

            if opp.detected and not off_hours:
                dedup_key = CacheKeys.autopilot_opportunity(lead.id)
                was_set = await redis.set(
                    dedup_key,
                    "1",
                    ttl=CacheTTL.AUTOPILOT_OPPORTUNITY,
                    nx=True,
                )
                if was_set:
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    alert = build_opportunity_alert_text(
                        lead_id=lead.id,
                        lead_name=lead.name,
                        lead_phone=lead.phone or "\u2014",
                        score=score,
                        health_score=ci.health_score,
                        recommended_action_uz=opp.recommended_action_uz,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

            # ── 2. At-risk detection ──────────────────────────────
            risk = (
                detect_at_risk(signal_vector=sv)
                if sv
                else detect_at_risk(
                    score=score,
                    health_score=ci.health_score,
                    last_objection=mem.get("last_objection"),
                    objection_resolved=objection_resolved,
                    minutes_since_last_activity=mins_inactive,
                    lead_temperature=temp,
                    follow_up_count=lead.follow_up_count or 0,
                    closing_confidence=lead.closing_confidence,
                    current_stage=stage_str,
                )
            )

            # At-risk: critical = anytime, normal = business hours only
            if risk.detected and (not off_hours or risk.urgency == "critical"):
                dedup_key = CacheKeys.autopilot_risk(lead.id)
                was_set = await redis.set(
                    dedup_key,
                    "1",
                    ttl=CacheTTL.AUTOPILOT_RISK,
                    nx=True,
                )
                if was_set:
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    alert = build_at_risk_alert_text(
                        lead_id=lead.id,
                        lead_name=lead.name,
                        lead_phone=lead.phone or "\u2014",
                        risk_reason_uz=risk.risk_reason_uz,
                        recommended_action_uz=risk.recommended_action_uz,
                        urgency=risk.urgency,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

            # ── 3. Closing suggestion ─────────────────────────────
            closing = (
                suggest_closing_tactic(signal_vector=sv)
                if sv
                else suggest_closing_tactic(
                    score=score,
                    phone_captured=bool(lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    closing_confidence=lead.closing_confidence,
                    deal_probability_percent=dp_pct,
                    buyer_type=mem.get("buyer_type"),
                    lead_temperature=temp,
                    last_objection=mem.get("last_objection"),
                    closing_attempted=bool(mem.get("last_closing_attempt")),
                )
            )

            if closing.should_close and closing.confidence >= 0.70 and not off_hours:
                dedup_key = CacheKeys.autopilot_closing(lead.id)
                was_set = await redis.set(
                    dedup_key,
                    "1",
                    ttl=CacheTTL.AUTOPILOT_CLOSING,
                    nx=True,
                )
                if was_set:
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    tactic_label = CLOSING_TACTIC_LABELS.get(closing.tactic, closing.tactic)
                    alert = build_closing_alert_text(
                        lead_id=lead.id,
                        lead_name=lead.name,
                        tactic_uz=tactic_label,
                        reason_uz=closing.reason_uz,
                        suggested_message_uz=closing.suggested_message_uz,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

    except Exception:
        log.exception("sales_autopilot_error")
    finally:
        if bot:
            await bot.session.close()

    if alerts_sent:
        log.info("sales_autopilot_alerts", count=alerts_sent)


# ── Helpers ────────────────────────────────────────────────────────────────


def _classify_temp(score: int) -> str:
    """Derive temperature from score when DB field is empty."""
    if score >= 60:
        return "hot"
    if score >= 30:
        return "warm"
    return "cold"


async def _load_lead_memory(user_id: int) -> dict:
    """Load AI memory from Redis. Returns {} on error."""
    try:
        from apps.bot.handlers.private.ai_memory import _load_ai_memory

        return await _load_ai_memory(user_id) or {}
    except Exception:
        return {}


async def _get_lead_score(user_id: int) -> int:
    """Return lead score from Redis."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        raw = await get_redis().get(CacheKeys.ai_lead_score(user_id))
        return int(raw) if raw else 0
    except Exception:
        return 0
