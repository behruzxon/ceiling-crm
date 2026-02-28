"""
apps.bot.tasks.daily_report
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Background asyncio task: sends a daily CRM stats summary to the admin group
every day at 09:00 server local time.

Lifecycle
---------
- start(bot)  — called from on_startup; creates the asyncio.Task
- stop()       — called from on_shutdown; cancels the task cleanly

The loop sleeps until the next 09:00 wall-clock tick, fires the report,
then immediately sleeps again until the following day.  asyncio.CancelledError
is a BaseException, so the plain `except Exception` guard in _run() never
swallows it — the task exits cleanly when stop() is called.
"""
from __future__ import annotations

import asyncio
import datetime
from asyncio import Task
from typing import Optional

from aiogram import Bot

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_stats_service
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

_task: Optional[Task] = None  # type: ignore[type-arg]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _seconds_until_09() -> float:
    """Seconds from now until the next 09:00 in server local time."""
    now = datetime.datetime.now()
    target = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if now >= target:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


def _format_report(s: dict) -> str:  # type: ignore[type-arg]
    return (
        "📊 <b>Daily Report</b>\n\n"
        f"👥 Join:  <b>{s['group_joins']}</b>\n"
        f"🆕 Leads: <b>{s['new_leads']}</b>\n"
        f"🔥 Hot:   <b>{s['hot_leads']}</b>\n"
        f"🏆 Won:   <b>{s['won']}</b>\n"
        f"❌ Lost:  <b>{s['lost']}</b>\n\n"
        "📈 <b>Konversiya:</b>\n"
        f"👥→🆕  <b>{s['join_to_lead_conversion']}%</b>\n"
        f"🆕→🏆  <b>{s['lead_to_won_conversion']}%</b>\n"
        f"👥→🏆  <b>{s['join_to_won_conversion']}%</b>"
    )


# ── Core loop ──────────────────────────────────────────────────────────────────


async def _run(bot: Bot) -> None:
    settings = get_settings()
    chat_id = settings.bot.admin_group_id

    while True:
        wait = _seconds_until_09()
        log.info("daily_report_scheduled", wait_seconds=int(wait))

        # Sleeps until 09:00; CancelledError propagates here on stop()
        await asyncio.sleep(wait)

        try:
            factory = get_session_factory()
            async with factory() as session:
                stats = await get_stats_service(session).get_stats("today")
            await bot.send_message(chat_id=chat_id, text=_format_report(stats))
            log.info("daily_report_sent", chat_id=chat_id)
        except Exception:
            log.exception("daily_report_error")


# ── Public API ─────────────────────────────────────────────────────────────────


def start(bot: Bot) -> None:
    """Create and register the background daily-report task."""
    global _task
    _task = asyncio.create_task(_run(bot), name="daily_report")
    log.info("daily_report_task_started")


def stop() -> None:
    """Cancel the background task on bot shutdown."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        log.info("daily_report_task_cancelled")
    _task = None
