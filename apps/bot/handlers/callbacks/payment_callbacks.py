"""
apps.bot.handlers.callbacks.payment_callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin inline-keyboard callbacks for payment approval/rejection.

Callback data format:
  pay:a:<payment_id>:<user_id>   — approve
  pay:r:<payment_id>:<user_id>   — reject

Both values are integers; combined they stay well under Telegram's 64-byte limit.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_payment_service
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:payment")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_callback(data: str) -> tuple[int, int]:
    """Return (payment_id, user_id) from 'pay:a:123:456'."""
    parts = data.split(":")
    return int(parts[2]), int(parts[3])


async def _edit_admin_caption(callback: CallbackQuery, suffix: str) -> None:
    """Append decision suffix to admin message caption and remove inline keyboard."""
    msg = callback.message
    if msg is None:
        return
    old_caption = msg.caption or msg.text or ""
    try:
        await msg.edit_caption(
            caption=f"{old_caption}\n\n{suffix}",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        # Non-fatal: message may already be edited or too old
        log.warning("payment_admin_caption_edit_failed", callback_data=callback.data)


# ── Approve ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay:a:"))
async def cb_approve_payment(callback: CallbackQuery, **data: object) -> None:
    payment_id, user_id = _parse_callback(callback.data or "")

    factory = get_session_factory()
    async with factory() as session:
        svc = get_payment_service(session)
        try:
            await svc.mark_paid(payment_id)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("payment_approve_failed", payment_id=payment_id)
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            return

    log.info("payment_approved", payment_id=payment_id, by=callback.from_user and callback.from_user.id)

    # Notify client
    try:
        await callback.bot.send_message(  # type: ignore[union-attr]
            chat_id=user_id,
            text="✅ To'lovingiz tasdiqlandi.",
        )
    except Exception:
        log.warning("payment_approve_user_notify_failed", user_id=user_id)

    await _edit_admin_caption(callback, "✅ <b>Tasdiqlandi</b>")
    await callback.answer("✅ Tasdiqlandi")


# ── Reject ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay:r:"))
async def cb_reject_payment(callback: CallbackQuery, **data: object) -> None:
    payment_id, user_id = _parse_callback(callback.data or "")

    factory = get_session_factory()
    async with factory() as session:
        svc = get_payment_service(session)
        try:
            await svc.reject_payment(payment_id)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("payment_reject_failed", payment_id=payment_id)
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            return

    log.info("payment_rejected", payment_id=payment_id, by=callback.from_user and callback.from_user.id)

    # Notify client
    try:
        await callback.bot.send_message(  # type: ignore[union-attr]
            chat_id=user_id,
            text="❌ To'lovingiz rad etildi.",
        )
    except Exception:
        log.warning("payment_reject_user_notify_failed", user_id=user_id)

    await _edit_admin_caption(callback, "❌ <b>Rad etildi</b>")
    await callback.answer("❌ Rad etildi")
