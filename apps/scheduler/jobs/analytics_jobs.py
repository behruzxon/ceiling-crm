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
        hour=23,
        minute=59,
        id="analytics_daily",
        replace_existing=True,
    )
    # AI daily report — sent to admin group at 21:00 Tashkent time
    scheduler.add_job(
        send_ai_daily_report,
        trigger="cron",
        hour=21,
        minute=0,
        id="ai_daily_report",
        replace_existing=True,
    )
    # Daily admin summary — sent to admin group at 20:00 Tashkent time
    scheduler.add_job(
        send_daily_admin_summary,
        trigger="cron",
        hour=20,
        minute=0,
        id="daily_admin_summary",
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

    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys
    from shared.config import get_settings

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


# ── Daily Admin Summary ──────────────────────────────────────────────────────

_SOURCE_LABELS: dict[str, str] = {
    "group": "\U0001f465 Guruh",
    "site": "\U0001f310 Sayt",
    "ads": "\U0001f4e3 Reklama",
    "deeplink": "\U0001f517 Deeplink",
    "referral": "\U0001f91d Referral",
}

_REASON_LABELS: dict[str, str] = {
    "price": "\U0001f4b8 Narx",
    "competitor": "\u2694\ufe0f Raqobatchi",
    "no_response": "\U0001f4a4 Javob yo'q",
    "not_interested": "\U0001f645 Qiziqmagan",
    "other": "\U0001f4dd Boshqa",
}


async def send_daily_admin_summary() -> None:
    """Send evening CRM summary to admin group.

    Includes: new leads, conversions, lost leads, top source, active deals.
    Runs at 20:00 Tashkent time via scheduler.
    """
    import datetime as dt

    from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
    from infrastructure.database.session import get_session_factory
    from shared.config import get_settings

    settings = get_settings()
    admin_group_id = settings.bot.admin_group_id
    bot_token = settings.bot.token.get_secret_value()

    # Today 00:00 UTC
    now = dt.datetime.now(dt.UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    date_str = dt.date.today().isoformat()

    # ── Load stats from DB ───────────────────────────────────────────────────
    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            stats = await repo.get_daily_stats(today_start)
    except Exception:
        log.exception("daily_admin_summary_db_failed", date=date_str)
        return

    new_leads = stats["new_leads"]
    converted = stats["converted"]
    lost = stats["lost"]
    active = stats["active_deals"]
    top_source = stats["top_source"]
    lost_reasons = stats["lost_reasons"]

    rate = f"{(converted / new_leads * 100):.1f}%" if new_leads > 0 else "0%"
    src_label = _SOURCE_LABELS.get(top_source, top_source) if top_source else "\u2014"

    # ── Format summary ───────────────────────────────────────────────────────
    text = (
        "\U0001f4cb <b>KUNLIK XULOSA</b>\n\n"
        f"\U0001f195 Yangi lidlar: <b>{new_leads}</b>\n"
        f"\u2705 Konvertatsiya: <b>{converted}</b>\n"
        f"\U0001f4c8 Konversiya %: <b>{rate}</b>\n"
        f"\u274c Yo'qotilgan: <b>{lost}</b>\n"
        f"\U0001f504 Faol deallar: <b>{active}</b>\n"
        f"\U0001f4e1 Top manba: <b>{src_label}</b>\n"
    )

    if lost_reasons:
        text += "\n<b>\U0001f6ab Yo'qotish sabablari:</b>\n"
        for reason, count in lost_reasons.items():
            label = _REASON_LABELS.get(reason, reason)
            text += f"  {label}: {count}\n"

    text += f"\n\u23f0 Sana: {date_str}"

    # ── Send to admin group ──────────────────────────────────────────────────
    from aiogram import Bot

    bot: Bot | None = None
    try:
        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=admin_group_id,
            text=text,
            parse_mode="HTML",
        )
        log.info("daily_admin_summary_sent", date=date_str, new_leads=new_leads)
    except Exception:
        log.exception("daily_admin_summary_send_failed", date=date_str)
    finally:
        if bot:
            await bot.session.close()
