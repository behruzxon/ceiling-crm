"""
apps.bot.handlers.admin.sales_report
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/sales_report — Simple daily sales performance summary.

Access: ADMIN / SUPERADMIN roles.
"""
from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:sales_report")

_MGMT_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)

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


@router.message(Command("sales_report"), RoleFilter(*_MGMT_ROLES))
async def cmd_sales_report(message: Message, **data: object) -> None:
    """Show today's sales report."""
    try:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            stats = await repo.get_daily_stats(today_start)

        new_leads = stats["new_leads"]
        converted = stats["converted"]
        lost = stats["lost"]
        active = stats["active_deals"]
        top_source = stats["top_source"]
        lost_reasons = stats["lost_reasons"]

        # Conversion rate
        rate = f"{(converted / new_leads * 100):.1f}%" if new_leads > 0 else "0%"

        # Format top source
        src_label = _SOURCE_LABELS.get(top_source, top_source) if top_source else "\u2014"

        text = (
            "\U0001f4ca <b>Sales Report</b>\n\n"
            f"\U0001f195 Today Leads: <b>{new_leads}</b>\n"
            f"\u2705 Converted: <b>{converted}</b>\n"
            f"\U0001f4c8 Conversion Rate: <b>{rate}</b>\n"
            f"\u274c Lost Leads: <b>{lost}</b>\n"
            f"\U0001f504 Active Deals: <b>{active}</b>\n"
            f"\U0001f4e1 Top Source: <b>{src_label}</b>\n"
        )

        # Lost reasons breakdown
        if lost_reasons:
            text += "\n<b>\U0001f6ab Lost sabablari:</b>\n"
            for reason, count in lost_reasons.items():
                label = _REASON_LABELS.get(reason, reason)
                text += f"  {label}: {count}\n"

        await message.answer(text)

    except Exception:
        log.exception("sales_report_command_failed")
        await message.answer("\u274c Sales report xatolik yuz berdi.")
