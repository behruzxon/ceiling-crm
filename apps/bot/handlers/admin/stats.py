"""
apps.bot.handlers.admin.stats
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin /stats command — CRM metrics + group join counts.

Commands / entry points
-----------------------
  /stats                  — show period selector
  "📊 Statistika" button  — same as /stats (for keyboards that include it)
  stats:period:today      — inline button → edit with today's stats
  stats:period:7d         — inline button → edit with 7-day stats
  stats:period:30d        — inline button → edit with 30-day stats

RBAC: MANAGER | ADMIN | SUPERADMIN
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_stats_service
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:stats")

_MGMT_ROLES = (UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN)

_VALID_PERIODS = frozenset({"today", "7d", "30d"})
_PERIOD_LABELS = {"today": "Bugun", "7d": "7 kun", "30d": "30 kun"}


# ── Keyboard ───────────────────────────────────────────────────────────────────


def _period_keyboard(active: str | None = None) -> InlineKeyboardMarkup:
    """Row of three period buttons; the active one is prefixed with ✅."""

    def _btn(label: str, period: str) -> InlineKeyboardButton:
        text = f"✅ {label}" if period == active else label
        return InlineKeyboardButton(
            text=text, callback_data=f"stats:period:{period}"
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[[
            _btn("Bugun", "today"),
            _btn("7 kun", "7d"),
            _btn("30 kun", "30d"),
        ]]
    )


# ── Formatting ─────────────────────────────────────────────────────────────────


def _format_stats(s: dict) -> str:  # type: ignore[type-arg]
    period_label = _PERIOD_LABELS.get(s["period"], s["period"])
    return (
        f"📊 <b>Statistika — {period_label}</b>\n\n"
        f"👥 Guruhga qo'shildi:   <b>{s['group_joins']}</b>\n\n"
        f"📋 Yangi lidlar:        <b>{s['new_leads']}</b>\n"
        f"🔥 Hot lidlar:          <b>{s['hot_leads']}</b>\n"
        f"📐 O'lchov bosqichida:  <b>{s['measurement']}</b>\n"
        f"🏆 Won (yutildi):       <b>{s['won']}</b>\n"
        f"❌ Lost (yo'qotildi):   <b>{s['lost']}</b>\n\n"
        f"📈 <b>Konversiya:</b>\n"
        f"👥→🆕 Join→Lead:  <b>{s['join_to_lead_conversion']}%</b>\n"
        f"🆕→🏆 Lead→Won:   <b>{s['lead_to_won_conversion']}%</b>\n"
        f"👥→🏆 Join→Won:   <b>{s['join_to_won_conversion']}%</b>"
    )


# ── Handlers ───────────────────────────────────────────────────────────────────


@router.message(F.text == "📊 Statistika", RoleFilter(*_MGMT_ROLES))
@router.message(Command("stats"), RoleFilter(*_MGMT_ROLES))
async def cmd_stats(message: Message, **data: object) -> None:
    """Show the period-selector keyboard."""
    await message.answer(
        "📊 <b>Statistika</b>\n\nDavrni tanlang:",
        reply_markup=_period_keyboard(),
    )


@router.callback_query(
    F.data.startswith("stats:period:"),
    RoleFilter(*_MGMT_ROLES),
)
async def cb_stats_period(callback: CallbackQuery, **data: object) -> None:
    """Fetch and display stats for the chosen period."""
    period = (callback.data or "").split(":")[-1]
    if period not in _VALID_PERIODS:
        await callback.answer("Noto'g'ri davr", show_alert=True)
        return

    await callback.answer()

    factory = get_session_factory()
    try:
        async with factory() as session:
            stats = await get_stats_service(session).get_stats(period)
    except Exception:
        log.exception("stats_fetch_error", period=period)
        await callback.message.edit_text(  # type: ignore[union-attr]
            "❌ Statistikani olishda xatolik yuz berdi.",
            reply_markup=_period_keyboard(),
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        _format_stats(stats),
        reply_markup=_period_keyboard(active=period),
    )
