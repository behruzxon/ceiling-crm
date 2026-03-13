"""Follow-up funnel jobs — brain-driven + inactivity-based reminders."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_followup_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all follow-up automation jobs."""
    # Brain-driven follow-ups every 60s
    scheduler.add_job(
        check_due_followups,
        trigger="interval",
        seconds=60,
        id="check_due_followups",
        replace_existing=True,
    )
    # Inactivity-based reminders every 15 min
    scheduler.add_job(
        check_inactive_leads,
        trigger="interval",
        minutes=15,
        id="check_inactive_leads",
        replace_existing=True,
    )
    # HOT lead inactivity alert every 10 min
    scheduler.add_job(
        check_hot_lead_inactivity,
        trigger="interval",
        minutes=10,
        id="check_hot_lead_inactivity",
        replace_existing=True,
    )


async def check_due_followups() -> None:
    """Send admin reminders for leads whose next_follow_up_at is now overdue.

    User-facing follow-ups are deferred by the brain/service layer if they
    fall outside business hours.  This job still runs (to detect overdue
    leads) but the service handles the actual deferral.
    """
    from shared.config import get_settings
    from core.services.followup_service import FollowupService

    settings = get_settings()
    svc = FollowupService(
        bot_token=settings.bot.token.get_secret_value(),
        admin_user_id=settings.bot.admin_user_id,
    )
    count = await svc.process_due_followups()
    if count:
        log.info("followup_job_done", count=count)


async def check_inactive_leads() -> None:
    """Check for inactive leads and send tiered reminders.

    Tiers (based on BusinessSettings):
      - 24h inactivity → first reminder
      - 72h inactivity → second reminder
      - 7 days inactivity → mark as LOST candidate

    Normal alerts are suppressed during off-hours.
    LOST marking (internal) still runs anytime.
    """
    from datetime import datetime, timedelta, timezone

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
    from infrastructure.database.session import get_session_factory
    from shared.config import get_settings
    from shared.utils.business_hours import is_off_hours
    from shared.utils.telegram_send import safe_send_message

    settings = get_settings()
    admin_id = settings.bot.admin_user_id
    if not admin_id:
        return

    off_hours = is_off_hours()
    now = datetime.now(timezone.utc)
    h24 = settings.business.follow_up_day1_hours   # 24
    h72 = settings.business.follow_up_day3_hours   # 72
    h168 = settings.business.follow_up_day7_hours  # 168

    factory = get_session_factory()
    bot: Bot | None = None
    sent = 0

    try:
        async with factory() as session:
            repo = PostgresLeadRepository(session)

            # Get leads inactive for > 24h (includes 72h and 7d leads)
            cutoff_24h = now - timedelta(hours=h24)
            inactive = await repo.get_inactive_leads(cutoff_24h)

            if not inactive:
                return

            bot = Bot(
                token=settings.bot.token.get_secret_value(),
                default=DefaultBotProperties(parse_mode="HTML"),
            )

            for lead in inactive:
                hours_inactive = (now - lead.updated_at).total_seconds() / 3600

                if hours_inactive >= h168:
                    # 7 days → LOST candidate
                    # Only mark once (skip if already lost)
                    if lead.lead_status == "lost":
                        continue
                    await repo.update_lead_status(lead.id, "lost")
                    await repo.set_lost_reason(lead.id, "no_response")
                    text = (
                        "\u26a0\ufe0f <b>LOST candidate</b>\n\n"
                        f"\U0001f4cb Lid #{lead.id} — {lead.name}\n"
                        f"\U0001f4f1 {lead.phone}\n"
                        f"\u23f0 {int(hours_inactive)}h javobsiz\n"
                        f"\U0001f4a4 Sabab: no_response\n\n"
                        f"/lead_{lead.id}"
                    )
                    await safe_send_message(bot, admin_id, text)
                    sent += 1

                elif hours_inactive >= h72:
                    # 72h → second reminder (skip if already reminded twice)
                    if (lead.follow_up_count or 0) >= 2:
                        continue
                    # Normal alert — suppress during off-hours
                    if off_hours:
                        continue
                    text = (
                        "\U0001f534 <b>2-eslatma (72 soat)</b>\n\n"
                        f"\U0001f4cb Lid #{lead.id} — {lead.name}\n"
                        f"\U0001f4f1 {lead.phone}\n"
                        f"\U0001f4cd {lead.district}\n"
                        f"\u23f0 {int(hours_inactive)}h javobsiz\n\n"
                        f"/lead_{lead.id}"
                    )
                    await safe_send_message(bot, admin_id, text)
                    await repo.update_ai_scoring(
                        lead.id, increment_followup_count=True,
                    )
                    sent += 1

                elif hours_inactive >= h24:
                    # 24h → first reminder (skip if already reminded)
                    if (lead.follow_up_count or 0) >= 1:
                        continue
                    # Normal alert — suppress during off-hours
                    if off_hours:
                        continue
                    text = (
                        "\U0001f7e1 <b>1-eslatma (24 soat)</b>\n\n"
                        f"\U0001f4cb Lid #{lead.id} — {lead.name}\n"
                        f"\U0001f4f1 {lead.phone}\n"
                        f"\U0001f4cd {lead.district}\n"
                        f"\u23f0 {int(hours_inactive)}h javobsiz\n\n"
                        f"/lead_{lead.id}"
                    )
                    await safe_send_message(bot, admin_id, text)
                    await repo.update_ai_scoring(
                        lead.id, increment_followup_count=True,
                    )
                    sent += 1

            await session.commit()

    except Exception:
        log.exception("check_inactive_leads_error")
    finally:
        if bot:
            await bot.session.close()

    if sent:
        log.info("inactive_leads_processed", count=sent)


async def check_hot_lead_inactivity() -> None:
    """Send AI-powered suggestion to admin group for HOT leads inactive 2h+.

    Time-aware thresholds:
      - Business hours: 2h inactivity → alert
      - Off hours: 6h inactivity → alert (customers reply next morning)

    Deduped via Redis key: one alert per lead per 6 hours.
    """
    from datetime import datetime, timedelta, timezone

    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys
    from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
    from infrastructure.database.session import get_session_factory
    from shared.config import get_settings
    from shared.utils.business_hours import is_off_hours
    from shared.utils.telegram_send import safe_send_message

    settings = get_settings()
    admin_group_id = settings.bot.admin_group_id
    bot_token = settings.bot.token.get_secret_value()

    now = datetime.now(timezone.utc)
    # Smart inactivity: 6h during off-hours, 2h during business hours
    inactivity_hours = 6 if is_off_hours() else 2
    cutoff_2h = now - timedelta(hours=inactivity_hours)

    factory = get_session_factory()
    bot: Bot | None = None
    sent = 0

    try:
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            # Get leads inactive for 2h+ that are HOT
            inactive = await repo.get_inactive_leads(cutoff_2h)

        # Filter to HOT leads only
        hot_leads = [
            l for l in inactive
            if (l.lead_status or "").lower() in ("hot",)
            or (l.lead_temperature or "").lower() == "hot"
            or (l.score or 0) >= 60
        ]

        if not hot_leads:
            return

        redis = get_redis()
        bot = Bot(
            token=bot_token,
            default=DefaultBotProperties(parse_mode="HTML"),
        )

        for lead in hot_leads[:10]:  # cap at 10 per cycle
            # Dedup: one alert per lead per 6 hours
            dedup_key = f"hot_alert:2h:{lead.id}"
            if await redis.set(dedup_key, "1", ttl=21600, nx=True) is False:
                continue

            hours_inactive = (now - lead.updated_at).total_seconds() / 3600

            # Try to generate AI advice for suggested action
            suggested_action = "Bepul o'lchov uchun qo'ng'iroq qiling."
            try:
                from core.services.ai_sales_advice import generate_sales_advice

                stage_val = (
                    lead.current_stage.value
                    if hasattr(lead.current_stage, "value")
                    else str(lead.current_stage)
                )
                advice = await generate_sales_advice(
                    lead_id=lead.id,
                    lead_name=lead.name,
                    lead_phone=lead.phone,
                    lead_district=lead.district,
                    lead_score=lead.score or 0,
                    lead_classification="hot",
                    pipeline_stage=stage_val,
                    room_area=float(lead.room_area) if lead.room_area else None,
                    package_type=lead.package_type,
                    closing_confidence=lead.closing_confidence,
                    hours_inactive=hours_inactive,
                )
                if advice.recommended_actions:
                    suggested_action = advice.recommended_actions[0]
            except Exception:
                pass  # fallback to default suggestion

            text = (
                "\U0001f525 <b>Hot Lead Alert</b>\n\n"
                f"\U0001f4cb Lead: #{lead.id}\n"
                f"\U0001f464 {lead.name} | {lead.phone}\n"
                f"\U0001f4cd {lead.district}\n"
                f"\u23f0 Last message: {hours_inactive:.0f}h ago\n\n"
                f"<b>Suggested action:</b>\n{suggested_action}\n\n"
                f"/lead_advice {lead.id}"
            )

            await safe_send_message(bot, admin_group_id, text)
            sent += 1

    except Exception:
        log.exception("check_hot_lead_inactivity_error")
    finally:
        if bot:
            await bot.session.close()

    if sent:
        log.info("hot_lead_alerts_sent", count=sent)
