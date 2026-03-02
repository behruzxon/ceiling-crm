"""Follow-up funnel job — runs every 60 seconds."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_followup_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all follow-up automation jobs."""
    scheduler.add_job(
        check_due_followups,
        trigger="interval",
        seconds=60,
        id="check_due_followups",
        replace_existing=True,
    )


async def check_due_followups() -> None:
    """Send admin reminders for leads whose next_follow_up_at is now overdue."""
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
