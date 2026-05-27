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
from shared.config import get_settings
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
        return InlineKeyboardButton(text=text, callback_data=f"stats:period:{period}")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("Bugun", "today"),
                _btn("7 kun", "7d"),
                _btn("30 kun", "30d"),
            ]
        ]
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
    """Show the period-selector keyboard.

    If invoked from the admin group directly, replies in-place.
    If invoked from a private DM or any other chat, posts the stats card
    to the admin group and sends a short acknowledgement to the caller.
    """
    admin_group_id = get_settings().bot.admin_group_id
    text = "📊 <b>Statistika</b>\n\nDavrni tanlang:"
    kb = _period_keyboard()

    if message.chat.id == admin_group_id:
        # Already in the admin group — reply here directly.
        await message.answer(text, reply_markup=kb)
        return

    # Invoked from outside the admin group (e.g. private DM).
    # Post the interactive card to the admin group; ack in current chat.
    if not admin_group_id:
        log.warning("stats_admin_group_id_not_set")
        await message.answer(text, reply_markup=kb)
        return

    try:
        await message.bot.send_message(  # type: ignore[union-attr]
            chat_id=admin_group_id, text=text, reply_markup=kb
        )
        log.info("stats_sent_to_admin_group", chat_id=admin_group_id)
        await message.answer("📊 Statistika admin guruhiga yuborildi.")
    except Exception:
        log.exception("stats_send_to_group_failed", chat_id=admin_group_id)
        # Fallback: show in current chat so admin isn't left without a response.
        await message.answer(text, reply_markup=kb)


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
