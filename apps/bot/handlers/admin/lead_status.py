"""
Admin quick-status callbacks for lead notification cards.

Callback pattern: lead:{id}:status:{status}
Supported statuses: contacted | measurement | quoted | deal | lost
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:lead_status")

# Map status slug → human-readable confirmation label
_STATUS_LABELS: dict[str, str] = {
    "contacted":   "✅ Bog'lanildi",
    "measurement": "📅 O'lchov belgilandi",
    "quoted":      "💰 Narx yuborildi",
    "deal":        "🧾 Zakaz rasmiylashtirildi",
    "lost":        "❌ Yo'qotildi",
}

# Terminal statuses: clear next_follow_up_at so scheduler stops sending reminders
_TERMINAL_STATUSES: frozenset[str] = frozenset({"deal", "lost"})

_CB_RE = re.compile(r"^lead:(\d+):status:(\w+)$")


@router.callback_query(F.data.regexp(_CB_RE))
async def cb_lead_status_update(callback: CallbackQuery, **data: object) -> None:
    """Update lead status when admin taps a quick-action button on a lead card."""
    await callback.answer()
    if callback.data is None:
        return

    m = _CB_RE.match(callback.data)
    if not m:
        return

    lead_id = int(m.group(1))
    new_status = m.group(2)

    if new_status not in _STATUS_LABELS:
        await callback.answer("Noto'g'ri status.", show_alert=True)
        return

    _tid = data.get("tenant_id")
    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session, tenant_id=_tid)
            await repo.update_lead_status(lead_id, new_status)
            if new_status in _TERMINAL_STATUSES:
                # Explicitly clear follow-up schedule for terminal states
                await repo.update_ai_scoring(lead_id, next_follow_up_at=None)
            await session.commit()
        log.info("lead_status_updated", lead_id=lead_id, new_status=new_status)
    except Exception:
        log.exception("lead_status_update_failed", lead_id=lead_id)
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    label = _STATUS_LABELS[new_status]
    await callback.answer(label, show_alert=False)

    # Append status tag to the original card so admin sees it was actioned
    if callback.message:
        try:
            original = callback.message.text or callback.message.caption or ""
            await callback.message.edit_text(
                original + f"\n\n<b>Status: {label}</b>",
                reply_markup=None,
            )
        except Exception:
            pass  # message too old or already edited — silently ignore
