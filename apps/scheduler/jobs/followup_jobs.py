"""Follow-up funnel job definitions (D+1, D+3, D+7)."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shared.logging import get_logger

log = get_logger(__name__)


def register_followup_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register all follow-up automation jobs."""
    scheduler.add_job(
        check_new_leads_alert,
        trigger="interval",
        minutes=5,
        id="check_new_leads",
        replace_existing=True,
    )


async def check_new_leads_alert() -> None:
    """Alert admins about NEW leads with no contact for >30 minutes. TODO: implement."""
    raise NotImplementedError


async def send_followup_day1(lead_id: int) -> None:
    """Send D+1 follow-up message to client. TODO: implement via BroadcastService."""
    raise NotImplementedError


async def send_followup_day3(lead_id: int) -> None:
    """Send D+3 follow-up message. TODO: implement."""
    raise NotImplementedError


async def send_followup_day7(lead_id: int) -> None:
    """Send D+7 final follow-up. TODO: implement."""
    raise NotImplementedError
