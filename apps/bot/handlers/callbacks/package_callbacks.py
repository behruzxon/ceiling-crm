"""
apps.bot.handlers.callbacks.package_callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin inline-button callbacks for package lead notifications.

Callback prefixes handled here
-------------------------------
  pkg:admin:hot:{lead_id}      — mark lead_status = hot
  pkg:admin:warm:{lead_id}     — mark lead_status = warm
  pkg:admin:cold:{lead_id}     — mark lead_status = cold
  pkg:admin:phone:{lead_id}    — show lead phone as alert
  pkg:admin:schedule:{lead_id} — advance lead to MEASUREMENT stage
  pkg:admin:note:{lead_id}     — prompt admin to add a note
  pkg:admin:block:{lead_id}    — block user + mark lead blocked

All callbacks write audit-level log entries and update the notification
message to reflect the new state.
"""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.database.models.lead import LeadModel
from infrastructure.database.models.user import UserModel
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.repositories.pipeline_repo import PostgresPipelineRepository
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_action_repo
from shared.constants.enums import PipelineStage
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:packages")

# ── Status display helpers ─────────────────────────────────────────────────────

_STATUS_EMOJI = {"hot": "🔥", "warm": "🟡", "cold": "❄️", "blocked": "🚫"}
_STATUS_LABEL = {"hot": "HOT", "warm": "WARM", "cold": "COLD", "blocked": "BLOCKED"}


def _updated_keyboard(lead_id: int, status: str) -> InlineKeyboardMarkup:
    """Return admin action keyboard with the current status highlighted in text."""
    lid = lead_id
    se = _STATUS_EMOJI.get(status, "⬜")
    sl = _STATUS_LABEL.get(status, status.upper())
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"✅ HOT{'  ←' if status == 'hot' else ''}",
                callback_data=f"pkg:admin:hot:{lid}",
            ),
            InlineKeyboardButton(
                text=f"🟡 WARM{'  ←' if status == 'warm' else ''}",
                callback_data=f"pkg:admin:warm:{lid}",
            ),
            InlineKeyboardButton(
                text=f"❄️ COLD{'  ←' if status == 'cold' else ''}",
                callback_data=f"pkg:admin:cold:{lid}",
            ),
        ],
        [
            InlineKeyboardButton(text="📞 Telefon",  callback_data=f"pkg:admin:phone:{lid}"),
            InlineKeyboardButton(text="📅 O'lchov", callback_data=f"pkg:admin:schedule:{lid}"),
        ],
        [
            InlineKeyboardButton(text="📝 Izoh",  callback_data=f"pkg:admin:note:{lid}"),
            InlineKeyboardButton(text="🚫 Block", callback_data=f"pkg:admin:block:{lid}"),
        ],
        [InlineKeyboardButton(
            text=f"{se} Holat: {sl}",
            callback_data=f"pkg:admin:noop:{lid}",
        )],
    ])


# ── Shared utilities ───────────────────────────────────────────────────────────

def _parse_lead_id(callback_data: str) -> int | None:
    parts = (callback_data or "").split(":")
    if len(parts) < 4:
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


async def _get_lead_model(session, lead_id: int) -> LeadModel | None:
    return await session.get(LeadModel, lead_id)


# ── Callbacks ──────────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("pkg:admin:noop:"))
async def cb_noop(callback: CallbackQuery, **data: object) -> None:
    """Status display button — no action."""
    await callback.answer()


@router.callback_query(F.data.startswith("pkg:admin:hot:"))
@router.callback_query(F.data.startswith("pkg:admin:warm:"))
@router.callback_query(F.data.startswith("pkg:admin:cold:"))
async def cb_set_status(callback: CallbackQuery, **data: object) -> None:
    """Mark lead status as hot / warm / cold."""
    cd = callback.data  # type: ignore[union-attr]
    parts = cd.split(":")
    new_status = parts[2]   # hot | warm | cold
    lead_id = _parse_lead_id(cd)
    if lead_id is None:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return

    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            lead_repo = PostgresLeadRepository(session)
            await lead_repo.update_lead_status(lead_id, new_status)
            await get_lead_action_repo(session).insert(lead_id, actor_id, new_status)
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("pkg_admin_set_status_error", lead_id=lead_id, status=new_status)
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            return

    log.info(
        "pkg_admin_status_changed",
        lead_id=lead_id,
        actor_id=actor_id,
        new_status=new_status,
    )

    emoji = _STATUS_EMOJI.get(new_status, "⬜")
    await callback.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=_updated_keyboard(lead_id, new_status)
    )
    await callback.answer(f"{emoji} Holat: {new_status.upper()}")

    # HOT alert when admin manually marks a lead hot (deduped internally)
    if new_status == "hot":
        try:
            from infrastructure.di import get_lead_notification_service
            await get_lead_notification_service().notify_hot_lead(lead_id)
        except Exception:
            log.exception("pkg_hot_lead_notify_error", lead_id=lead_id)


@router.callback_query(F.data.startswith("pkg:admin:phone:"))
async def cb_show_phone(callback: CallbackQuery, **data: object) -> None:
    """Show lead's phone number as an alert."""
    lead_id = _parse_lead_id(callback.data)  # type: ignore[union-attr]
    if lead_id is None:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return

    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        model = await _get_lead_model(session, lead_id)
        if model is None:
            await callback.answer("Lead topilmadi", show_alert=True)
            return
        phone = model.phone or "—"
        await get_lead_action_repo(session).insert(lead_id, actor_id, "phone")
        await session.commit()

    await callback.answer(f"📱 Telefon: {phone}", show_alert=True)


@router.callback_query(F.data.startswith("pkg:admin:schedule:"))
async def cb_schedule_measurement(callback: CallbackQuery, **data: object) -> None:
    """Advance lead to MEASUREMENT stage and confirm."""
    lead_id = _parse_lead_id(callback.data)  # type: ignore[union-attr]
    if lead_id is None:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return

    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            pipeline_repo = PostgresPipelineRepository(session)
            await pipeline_repo.insert_stage(
                lead_id=lead_id,
                stage=PipelineStage.MEASUREMENT,
                changed_by=actor_id,
                note="O'lchov tayinlandi (admin paneldan)",
            )
            await get_lead_action_repo(session).insert(lead_id, actor_id, "measurement")
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("pkg_admin_schedule_error", lead_id=lead_id)
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            return

    log.info("pkg_admin_measurement_scheduled", lead_id=lead_id, actor_id=actor_id)
    await callback.answer("📅 O'lchov bosqichiga o'tkazildi!", show_alert=True)


@router.callback_query(F.data.startswith("pkg:admin:note:"))
async def cb_add_note(callback: CallbackQuery, **data: object) -> None:
    """Prompt admin to use /note_{lead_id} command for adding a note."""
    lead_id = _parse_lead_id(callback.data)  # type: ignore[union-attr]
    if lead_id is None:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return

    actor_id = callback.from_user.id  # type: ignore[union-attr]
    factory = get_session_factory()
    async with factory() as session:
        await get_lead_action_repo(session).insert(lead_id, actor_id, "note")
        await session.commit()

    await callback.answer(
        f"📝 Izoh qo'shish uchun yozing:\n/note_{lead_id} <matn>",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("pkg:admin:block:"))
async def cb_block_lead(callback: CallbackQuery, **data: object) -> None:
    """Block the lead's user (is_blocked=true) and update lead_status."""
    lead_id = _parse_lead_id(callback.data)  # type: ignore[union-attr]
    if lead_id is None:
        await callback.answer("Noto'g'ri so'rov", show_alert=True)
        return

    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            model = await _get_lead_model(session, lead_id)
            if model is None:
                await callback.answer("Lead topilmadi", show_alert=True)
                return

            # Block the user account
            await session.execute(
                sa.update(UserModel)
                .where(UserModel.id == model.user_id)
                .values(is_blocked=True, updated_at=datetime.now(UTC))
            )
            # Mark lead as blocked
            await session.execute(
                sa.update(LeadModel)
                .where(LeadModel.id == lead_id)
                .values(lead_status="blocked", updated_at=datetime.now(UTC))
            )
            await get_lead_action_repo(session).insert(lead_id, actor_id, "block")
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("pkg_admin_block_error", lead_id=lead_id)
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            return

    log.info("pkg_admin_lead_blocked", lead_id=lead_id, actor_id=actor_id)
    await callback.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=_updated_keyboard(lead_id, "blocked")
    )
    await callback.answer("🚫 Foydalanuvchi bloklandi")
