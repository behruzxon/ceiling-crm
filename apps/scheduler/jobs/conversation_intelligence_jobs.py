"""Conversation intelligence jobs — health analysis, cooling, manager delay alerts."""
from __future__ import annotations

from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_conversation_intelligence_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all conversation intelligence jobs."""
    # Full conversation health scan every 10 min
    scheduler.add_job(
        check_conversation_health,
        trigger="interval",
        minutes=10,
        id="check_conversation_health",
        replace_existing=True,
    )
    # Manager response delay check every 5 min
    scheduler.add_job(
        check_manager_response_delay,
        trigger="interval",
        minutes=5,
        id="check_manager_response_delay",
        replace_existing=True,
    )


async def check_conversation_health() -> None:
    """Analyze active leads, detect risks, send insight + cooling alerts.

    Covers Phase 12 tasks: Conversation Analyzer, Lead Cooling Detection,
    Admin Insight Alerts, Smart Follow-Up Suggestions.

    Normal alerts are suppressed during off-hours to avoid midnight noise.
    Critical alerts (health <= 30) are sent anytime.
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

    off_hours = is_off_hours()
    now = datetime.now(UTC)
    now_ts = int(now.timestamp())

    factory = get_session_factory()
    bot: Bot | None = None
    alerts_sent = 0

    try:
        # Load active leads
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            leads = await repo.get_active_leads(limit=50)

        if not leads:
            return

        redis = get_redis()
        bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )

        from core.services.conversation_intelligence_service import (
            analyze_conversation,
            build_cooling_alert,
            build_insight_alert,
        )

        for lead in leads:
            # Load AI memory from Redis for enrichment
            mem = await _load_lead_memory(lead.user_id)
            score = await _get_lead_score(lead.user_id)

            # Compute minutes since last activity
            last_activity_ts = mem.get("last_activity_ts") or mem.get("updated_at")
            if last_activity_ts:
                minutes_inactive = max(0, (now_ts - int(last_activity_ts)) // 60)
            else:
                minutes_inactive = int(
                    (now - lead.updated_at).total_seconds() / 60
                )

            # Run conversation analysis
            result = analyze_conversation(
                score=score,
                last_objection=mem.get("last_objection"),
                last_objection_severity=mem.get("last_objection_severity"),
                last_user_message=mem.get("last_user_message"),
                phone_captured=bool(mem.get("phone_captured")),
                area_m2=mem.get("area_m2"),
                minutes_since_last_activity=minutes_inactive,
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=lead.lead_temperature or _classify_temp(score),
                closing_confidence=lead.closing_confidence,
                buyer_type=mem.get("buyer_type"),
                last_negotiation_tactic=mem.get("last_negotiation_tactic"),
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
                has_district=bool(lead.district),
                last_closing_attempt=mem.get("last_closing_attempt"),
                lead_status=lead.lead_status,
                current_stage=(
                    lead.current_stage.value
                    if hasattr(lead.current_stage, "value")
                    else str(lead.current_stage)
                ),
            )

            # ── Cooling alert (normal — business hours only) ────────────
            if result.cooling_detected and not off_hours:
                dedup_key = CacheKeys.conv_cooling_alert(lead.id)
                was_set = await redis.set(
                    dedup_key, "1", ttl=CacheTTL.CONV_COOLING_ALERT, nx=True,
                )
                if was_set:
                    temp = lead.lead_temperature or _classify_temp(score)
                    alert = build_cooling_alert(
                        lead_id=lead.id,
                        lead_name=lead.name,
                        lead_phone=lead.phone,
                        minutes_inactive=minutes_inactive,
                        lead_temperature=temp,
                        recommended_action_uz=result.recommended_action_uz,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

            # ── Insight alert: critical = anytime, high = business hours
            if result.risk_level == "critical" or (
                result.risk_level == "high" and not off_hours
            ):
                dedup_key = CacheKeys.conv_intel_alert(lead.id)
                was_set = await redis.set(
                    dedup_key, "1", ttl=CacheTTL.CONV_INTEL_ALERT, nx=True,
                )
                if was_set:
                    alert = build_insight_alert(
                        lead_id=lead.id,
                        lead_name=lead.name,
                        health_score=result.health_score,
                        signals=result.signals,
                        risk_level=result.risk_level,
                        recommended_action_uz=result.recommended_action_uz,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

            # Cap alerts per cycle
            if alerts_sent >= 8:
                break

    except Exception:
        log.exception("check_conversation_health_error")
    finally:
        if bot:
            await bot.session.close()

    if alerts_sent:
        log.info("conversation_health_alerts", count=alerts_sent)


async def check_manager_response_delay() -> None:
    """Detect slow manager responses to HOT/WARM leads and alert admin.

    A lead is flagged if the last activity (from user side) has been
    unanswered for longer than the threshold.

    Normal alert — suppressed during off-hours (managers aren't working).
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

    # Manager response delay is meaningless during off-hours
    if is_off_hours():
        return

    now_ts = int(datetime.now(UTC).timestamp())

    factory = get_session_factory()
    bot: Bot | None = None
    alerts_sent = 0

    try:
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            leads = await repo.get_active_leads(limit=30)

        if not leads:
            return

        redis = get_redis()

        from core.services.conversation_intelligence_service import (
            assess_manager_response,
        )

        for lead in leads:
            mem = await _load_lead_memory(lead.user_id)
            score = await _get_lead_score(lead.user_id)

            # Use last_activity_ts or updated_at
            last_ts = mem.get("last_activity_ts") or mem.get("updated_at")
            if not last_ts:
                continue

            minutes_since = max(0, (now_ts - int(last_ts)) // 60)

            assessment = assess_manager_response(
                minutes_since_user_message=minutes_since,
                lead_temperature=lead.lead_temperature or _classify_temp(score),
                score=score,
                lead_id=lead.id,
                lead_name=lead.name,
            )

            if not assessment.is_delayed:
                continue

            # Dedup
            dedup_key = CacheKeys.conv_mgr_delay_alert(lead.id)
            was_set = await redis.set(
                dedup_key, "1", ttl=CacheTTL.CONV_MGR_DELAY_ALERT, nx=True,
            )
            if not was_set:
                continue

            if not bot:
                bot = Bot(
                    token=bot_token,
                    default=DefaultBotProperties(parse_mode="HTML"),
                )

            await safe_send_message(bot, admin_group_id, assessment.alert_text)
            alerts_sent += 1

            if alerts_sent >= 5:
                break

    except Exception:
        log.exception("check_manager_response_delay_error")
    finally:
        if bot:
            await bot.session.close()

    if alerts_sent:
        log.info("manager_delay_alerts", count=alerts_sent)


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
        return await _load_ai_memory(user_id)
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
