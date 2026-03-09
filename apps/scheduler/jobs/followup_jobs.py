"""Follow-up automation jobs.

Two independent jobs:
  1. Admin reminders — every 60 s — sends lead cards to admin (existing)
  2. User follow-ups — every 180 s — sends staged re-engagement to users (new)
"""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from infrastructure.cache.distributed_lock import scheduler_lock
from shared.logging import get_logger

log = get_logger(__name__)


def register_followup_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all follow-up automation jobs."""
    # Existing: admin reminder cards
    scheduler.add_job(
        check_due_followups,
        trigger="interval",
        seconds=60,
        id="check_due_followups",
        replace_existing=True,
    )
    # New: user-facing staged re-engagement messages
    scheduler.add_job(
        check_user_followups,
        trigger="interval",
        seconds=180,
        id="check_user_followups",
        replace_existing=True,
    )


@scheduler_lock("check_due_followups", ttl=55)
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


@scheduler_lock("check_user_followups", ttl=170)
async def check_user_followups() -> None:
    """Send staged re-engagement messages to idle leads."""
    from core.services.user_followup_service import UserFollowupService
    from infrastructure.database.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        svc = UserFollowupService(session)
        result = await svc.process_due_user_followups()
        await session.commit()

    if result["sent"]:
        log.info("user_followups_processed", **result)
