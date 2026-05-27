"""Auto-sales monitoring jobs — stalled conversations, pending escalations."""

from __future__ import annotations

from datetime import UTC

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_auto_sales_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register auto-sales monitoring job."""
    scheduler.add_job(
        run_auto_sales_monitor,
        trigger="interval",
        minutes=10,
        id="run_auto_sales_monitor",
        replace_existing=True,
    )


async def run_auto_sales_monitor() -> None:
    """Monitor active leads for auto-sales state.

    Detects:
    - Conversations waiting for manager (escalated, no response >30 min)
    - Stalled auto-reply conversations (time-aware threshold)

    Time-aware stall detection:
      - Business hours: 60 min → stalled
      - Off hours: 180 min (3h) → stalled

    Sends deduped alerts to admin group (max 4 per cycle).
    Normal alerts suppressed during off-hours; critical escalations anytime.
    """
    import json
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
    # Time-aware stall threshold: 3h off-hours vs 60min business hours
    stall_threshold_minutes = 180 if off_hours else 60
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

        from core.services.auto_sales_service import (
            build_escalation_alert,
            build_stalled_conversation_alert,
            should_escalate,
        )
        from core.services.conversation_intelligence_service import (
            analyze_conversation,
        )

        for lead in leads:
            if alerts_sent >= 4:
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

            # Health score
            health_score = 50
            try:
                ci = analyze_conversation(
                    score=score,
                    last_objection=mem.get("last_objection"),
                    phone_captured=bool(lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    minutes_since_last_activity=mins_inactive,
                    follow_up_count=lead.follow_up_count or 0,
                    lead_temperature=temp,
                    closing_confidence=lead.closing_confidence,
                    buyer_type=mem.get("buyer_type"),
                    last_negotiation_tactic=mem.get("last_negotiation_tactic"),
                    has_district=bool(lead.district),
                    current_stage=stage_str,
                )
                health_score = ci.health_score
            except Exception:
                pass

            # Get auto-reply state from Redis
            consecutive = 0
            try:
                raw = await redis.get(CacheKeys.auto_reply_consecutive(lead.user_id))
                consecutive = int(raw) if raw else 0
            except Exception:
                pass

            # ── 1. Check escalation need ──────────────────────────────
            esc = should_escalate(
                last_objection=mem.get("last_objection"),
                objection_severity=mem.get("last_objection_severity"),
                consecutive_auto_replies=consecutive,
                health_score=health_score,
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
                follow_up_count=lead.follow_up_count or 0,
                score=score,
                closing_confidence=lead.closing_confidence,
            )

            if esc.should_escalate:
                # Escalations are critical — send anytime
                dedup_key = CacheKeys.auto_sales_escalation(lead.id)
                was_set = await redis.set(
                    dedup_key,
                    "1",
                    ttl=CacheTTL.AUTO_SALES_ESCALATION,
                    nx=True,
                )
                if was_set:
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    alert = build_escalation_alert(
                        lead_id=lead.id,
                        lead_name=lead.name or "?",
                        lead_phone=lead.phone or "\u2014",
                        reason_uz=esc.reason_uz,
                        last_message=mem.get("last_user_message", "\u2014")[:120],
                        suggested_action_uz=esc.suggested_action_uz,
                        urgency=esc.urgency,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

            # ── 2. Check stalled auto-reply conversations ─────────────
            # Normal alert — suppress during off-hours
            if consecutive > 0 and mins_inactive >= stall_threshold_minutes and not off_hours:
                # Auto-reply was sent but user hasn't responded in 60+ min
                dedup_key = f"autosell:stalled:{lead.id}"
                was_set = await redis.set(
                    dedup_key,
                    "1",
                    ttl=CacheTTL.AUTO_SALES_ESCALATION,
                    nx=True,
                )
                if was_set:
                    if not bot:
                        bot = Bot(
                            token=bot_token,
                            default=DefaultBotProperties(parse_mode="HTML"),
                        )
                    # Get last auto-reply type from log
                    last_type = "general_followup"
                    try:
                        log_raw = await redis.get(CacheKeys.auto_reply_log(lead.user_id))
                        if log_raw:
                            log_data = json.loads(log_raw)
                            last_type = log_data.get("reply_type", "general_followup")
                    except Exception:
                        pass

                    alert = build_stalled_conversation_alert(
                        lead_id=lead.id,
                        lead_name=lead.name or "?",
                        lead_phone=lead.phone or "\u2014",
                        minutes_waiting=mins_inactive,
                        last_auto_reply_type=last_type,
                    )
                    await safe_send_message(bot, admin_group_id, alert)
                    alerts_sent += 1

    except Exception:
        log.exception("auto_sales_monitor_error")
    finally:
        if bot:
            await bot.session.close()

    if alerts_sent:
        log.info("auto_sales_monitor_alerts", count=alerts_sent)


# ── Helpers ────────────────────────────────────────────────────────────────


def _classify_temp(score: int) -> str:
    if score >= 60:
        return "hot"
    if score >= 30:
        return "warm"
    return "cold"


async def _load_lead_memory(user_id: int) -> dict:
    try:
        from apps.bot.handlers.private.ai_memory import _load_ai_memory

        return await _load_ai_memory(user_id) or {}
    except Exception:
        return {}


async def _get_lead_score(user_id: int) -> int:
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        raw = await get_redis().get(CacheKeys.ai_lead_score(user_id))
        return int(raw) if raw else 0
    except Exception:
        return 0
