"""Daily analytics aggregation + AI activity report jobs."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shared.logging import get_logger

log = get_logger(__name__)

# ── Stat fields in the order they appear in the report ────────────────────────
_AI_STAT_FIELDS = (
    "users_started",
    "messages_total",
    "lead_hot",
    "lead_warm",
    "lead_cold",
    "phones_received",
    "orders_started",
)


def register_analytics_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register analytics scheduler jobs."""
    # Existing daily aggregation placeholder (23:59)
    scheduler.add_job(
        aggregate_daily_stats,
        trigger="cron",
        hour=23, minute=59,
        id="analytics_daily",
        replace_existing=True,
    )
    # AI daily report — sent to admin group at 21:00 Tashkent time
    scheduler.add_job(
        send_ai_daily_report,
        trigger="cron",
        hour=21, minute=0,
        id="ai_daily_report",
        replace_existing=True,
    )


async def aggregate_daily_stats() -> None:
    """Aggregate daily business metrics. TODO: implement via AnalyticsService."""
    log.debug("analytics_daily_not_implemented")


async def send_ai_daily_report() -> None:
    """
    Read today's AI stats from Redis, format a Uzbek-language report, and
    send it to the admin group.  Stats keys are date-partitioned and expire
    after 48 h, so no explicit reset is needed.

    Redis keys read: ai:stats:{YYYY-MM-DD}:{field}
    Sent to:        settings.bot.admin_group_id
    Timezone:       Asia/Tashkent (inherited from scheduler)
    """
    import datetime
    from shared.config import get_settings
    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys

    settings = get_settings()
    admin_group_id = settings.bot.admin_group_id
    bot_token = settings.bot.token.get_secret_value()

    date_str = datetime.date.today().isoformat()

    # ── Read counters ──────────────────────────────────────────────────────────
    try:
        redis = get_redis()
        stats: dict[str, int] = {}
        for field in _AI_STAT_FIELDS:
            raw = await redis.get(CacheKeys.ai_stats_field(date_str, field))
            stats[field] = int(raw) if raw else 0
    except Exception:
        log.exception("ai_daily_report_redis_failed", date=date_str)
        return

    # ── Conversion rate (phones / users, guard div-by-zero) ───────────────────
    users = stats["users_started"] or 1
    phones = stats["phones_received"]
    conversion = round(phones / users * 100, 1)

    # ── Format report ──────────────────────────────────────────────────────────
    text = (
        "📊 <b>KUNLIK HISOBOT</b>\n\n"
        f"👥 Yangi userlar: <b>{stats['users_started']}</b>\n"
        f"💬 Jami suhbatlar: <b>{stats['messages_total']}</b>\n\n"
        f"🔥 HOT lead: <b>{stats['lead_hot']}</b>\n"
        f"🟡 WARM lead: <b>{stats['lead_warm']}</b>\n"
        f"❄️ COLD lead: <b>{stats['lead_cold']}</b>\n\n"
        f"📞 Telefon qoldirganlar: <b>{stats['phones_received']}</b>\n"
        f"📦 Zakaz bosqichiga o'tganlar: <b>{stats['orders_started']}</b>\n\n"
        f"📈 Konversiya: <b>{conversion}%</b>\n\n"
        f"⏰ Sana: {date_str}"
    )

    # ── Send to admin group ────────────────────────────────────────────────────
    from aiogram import Bot
    bot: Bot | None = None
    try:
        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=admin_group_id,
            text=text,
            parse_mode="HTML",
        )
        log.info(
            "ai_daily_report_sent",
            date=date_str,
            users=stats["users_started"],
            phones=stats["phones_received"],
            conversion=conversion,
        )
    except Exception:
        log.exception("ai_daily_report_send_failed", date=date_str)
    finally:
        if bot:
            await bot.session.close()
