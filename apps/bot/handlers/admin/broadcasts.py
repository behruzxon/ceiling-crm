"""
Admin broadcast composer — private chat only, restricted to BOT_ADMIN_USER_ID.

FSM flow
--------
  "📣 Rassilka"
    └─► choosing_segment   ← inline: ALL / BY_STAGE / ADMIN_GROUPS
          ├─► choosing_stage   (only for BY_STAGE)
          └─► choosing_payload ← inline: TEXT / PHOTO / VIDEO / DOCUMENT
                ├─► waiting_for_text   (text payload)
                └─► waiting_for_media  (photo/video/document)
                      └─► confirming   ← preview + Yuborish / Bekor
                            └─ [create DB record, enqueue Celery worker]
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.bot.keyboards.broadcast import (
    confirm_keyboard,
    payload_keyboard,
    segment_keyboard,
    stage_keyboard,
)
from apps.bot.keyboards.main_menu import main_menu_keyboard
from apps.bot.states.broadcast import BroadcastStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_broadcast_service
from infrastructure.queue.tasks.broadcast_tasks import process_broadcast_batch
from shared.config import get_settings
from shared.constants.enums import PayloadType, SegmentType
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:broadcasts")

# ── helpers ────────────────────────────────────────────────────────────────────

_SEGMENT_LABELS: dict[str, str] = {
    "all": "👥 Barcha foydalanuvchilar",
    "stage": "🔀 Bosqich bo'yicha",
    "groups": "📢 Admin guruhlar",
}

_PAYLOAD_LABELS: dict[str, str] = {
    "text": "✍️ Matn",
    "photo": "🖼 Rasm",
    "video": "🎥 Video",
    "document": "📄 Hujjat",
}

_SEGMENT_TYPE_MAP: dict[str, SegmentType] = {
    "all": SegmentType.ALL_PRIVATE,
    "stage": SegmentType.LEAD_STAGE,
    "groups": SegmentType.ADMIN_GROUPS,
}

_PAYLOAD_TYPE_MAP: dict[str, PayloadType] = {
    "text": PayloadType.TEXT,
    "photo": PayloadType.PHOTO,
    "video": PayloadType.VIDEO,
    "document": PayloadType.DOCUMENT,
}


def _is_bot_admin(user_id: int) -> bool:
    settings = get_settings()
    return settings.bot.admin_user_id is not None and user_id == settings.bot.admin_user_id


async def _cancel_flow(message: Message | CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    target = message if isinstance(message, Message) else message.message
    if target:
        await target.answer(
            "❌ Rassilka bekor qilindi.",
            reply_markup=main_menu_keyboard(is_admin=True),
        )


# ── entry point ────────────────────────────────────────────────────────────────


@router.message(
    F.chat.type == "private",
    F.text == "📣 Rassilka",
)
async def cmd_broadcast_entry(message: Message, state: FSMContext, **data: object) -> None:
    """Entry from the admin main-menu button."""
    user_id = message.from_user.id if message.from_user else 0

    if not _is_bot_admin(user_id):
        await message.answer("⛔ Bu funksiya faqat bot admini uchun.")
        return

    await state.clear()
    await state.set_state(BroadcastStates.choosing_segment)
    await message.answer(
        "📣 <b>Yangi rassilka</b>\n\n" "Qaysi auditoriyaga yubormoqchisiz?",
        reply_markup=segment_keyboard(),
    )


# ── segment step ───────────────────────────────────────────────────────────────


@router.callback_query(
    F.message.chat.type == "private",
    StateFilter(BroadcastStates.choosing_segment),
    F.data.startswith("bcast:seg:"),
)
async def cb_choose_segment(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    seg_key = (callback.data or "").split("bcast:seg:", 1)[1]
    await callback.answer()

    if seg_key == "stage":
        await state.update_data(segment_key=seg_key)
        await state.set_state(BroadcastStates.choosing_stage)
        await callback.message.edit_text(
            "🔀 Qaysi bosqichdagi mijozlarga yubormoqchisiz?",
            reply_markup=stage_keyboard(),
        )
    else:
        await state.update_data(segment_key=seg_key, lead_stage=None)
        await state.set_state(BroadcastStates.choosing_payload)
        await callback.message.edit_text(
            f"✅ Segment: <b>{_SEGMENT_LABELS[seg_key]}</b>\n\n"
            "Qanday turdagi xabar yubormoqchisiz?",
            reply_markup=payload_keyboard(),
        )


@router.callback_query(
    F.message.chat.type == "private",
    StateFilter(BroadcastStates.choosing_stage),
    F.data.startswith("bcast:stage:"),
)
async def cb_choose_stage(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    stage_value = (callback.data or "").split("bcast:stage:", 1)[1]
    await callback.answer()
    await state.update_data(lead_stage=stage_value)
    await state.set_state(BroadcastStates.choosing_payload)
    await callback.message.edit_text(
        f"✅ Segment: <b>Bosqich bo'yicha ({stage_value})</b>\n\n"
        "Qanday turdagi xabar yubormoqchisiz?",
        reply_markup=payload_keyboard(),
    )


@router.callback_query(
    F.message.chat.type == "private",
    StateFilter(BroadcastStates.choosing_stage),
    F.data == "bcast:back:seg",
)
async def cb_back_to_segment(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    await callback.answer()
    await state.set_state(BroadcastStates.choosing_segment)
    await callback.message.edit_text(
        "📣 Qaysi auditoriyaga yubormoqchisiz?",
        reply_markup=segment_keyboard(),
    )


# ── payload type step ──────────────────────────────────────────────────────────


@router.callback_query(
    F.message.chat.type == "private",
    StateFilter(BroadcastStates.choosing_payload),
    F.data.startswith("bcast:pay:"),
)
async def cb_choose_payload(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    pay_key = (callback.data or "").split("bcast:pay:", 1)[1]
    await callback.answer()
    await state.update_data(payload_key=pay_key)

    if pay_key == "text":
        await state.set_state(BroadcastStates.waiting_for_text)
        await callback.message.edit_text(
            "✍️ Xabar matnini yuboring (HTML formatini qo'llab-quvvatlaydi):"
        )
    else:
        await state.set_state(BroadcastStates.waiting_for_media)
        type_hint = {"photo": "rasm", "video": "video", "document": "hujjat"}[pay_key]
        await callback.message.edit_text(
            f"📎 {type_hint.capitalize()} yuboring.\n"
            "<i>Izoh (caption) ixtiyoriy — rasmdan keyin alohida yubormang, "
            "to'g'ridan-to'g'ri media bilan birga yozing.</i>"
        )


# ── content collection ─────────────────────────────────────────────────────────


@router.message(
    StateFilter(BroadcastStates.waiting_for_text),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_text_content(message: Message, state: FSMContext, **data: object) -> None:
    await state.update_data(text=message.text, file_id=None)
    await _show_preview(message, state)


@router.message(
    StateFilter(BroadcastStates.waiting_for_media),
    F.photo | F.video | F.document,
)
async def handle_media_content(message: Message, state: FSMContext, **data: object) -> None:
    fsm = await state.get_data()
    pay_key = fsm.get("payload_key", "photo")

    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.document:
        file_id = message.document.file_id
    else:
        await message.answer("Iltimos, media faylni yuboring.")
        return

    caption = message.caption or ""
    await state.update_data(file_id=file_id, text=caption)
    await _show_preview(message, state)


async def _show_preview(message: Message, state: FSMContext) -> None:
    """Build preview text, estimate targets, show confirm keyboard."""
    fsm = await state.get_data()
    seg_key = fsm.get("segment_key", "all")
    pay_key = fsm.get("payload_key", "text")
    lead_stage = fsm.get("lead_stage")
    text_content: str = fsm.get("text") or ""

    seg_label = _SEGMENT_LABELS.get(seg_key, seg_key)
    if lead_stage:
        seg_label += f" [{lead_stage}]"
    pay_label = _PAYLOAD_LABELS.get(pay_key, pay_key)

    # Estimate reach
    count: int | str = "?"
    try:
        segment_type = _SEGMENT_TYPE_MAP[seg_key]
        factory = get_session_factory()
        async with factory() as session:
            svc = get_broadcast_service(session)
            count = await svc.estimate_reach_v2(segment_type, lead_stage)
    except Exception:
        log.exception("broadcast_reach_estimate_failed")

    preview = text_content[:200] + ("…" if len(text_content) > 200 else "")
    await state.set_state(BroadcastStates.confirming)
    await message.answer(
        "📋 <b>Rassilka ko'rinishi</b>\n\n"
        f"🎯 Segment:  <b>{seg_label}</b>\n"
        f"📦 Tur:      <b>{pay_label}</b>\n"
        f"👥 Maqsad:   <b>~{count} ta</b>\n\n"
        + (f"📝 Matn:\n<i>{preview}</i>" if preview else "<i>(Faqat media)</i>")
        + "\n\n"
        "Tasdiqlaysizmi?",
        reply_markup=confirm_keyboard(),
    )


# ── confirm / cancel ───────────────────────────────────────────────────────────


@router.callback_query(
    F.message.chat.type == "private",
    StateFilter(BroadcastStates.confirming),
    F.data == "bcast:confirm",
)
async def cb_confirm(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    await callback.answer()
    fsm = await state.get_data()

    seg_key = fsm.get("segment_key", "all")
    pay_key = fsm.get("payload_key", "text")
    lead_stage: str | None = fsm.get("lead_stage")
    text_content: str | None = fsm.get("text")
    file_id: str | None = fsm.get("file_id")

    segment_type = _SEGMENT_TYPE_MAP.get(seg_key, SegmentType.ALL_PRIVATE)
    payload_type = _PAYLOAD_TYPE_MAP.get(pay_key, PayloadType.TEXT)
    created_by = callback.from_user.id if callback.from_user else 0

    broadcast_id: int | None = None
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = get_broadcast_service(session)
            broadcast_id = await svc.create_broadcast_v2(
                segment_type=segment_type,
                payload_type=payload_type,
                text=text_content,
                file_id=file_id,
                created_by=created_by,
                lead_stage=lead_stage,
            )
            await session.commit()
    except Exception:
        log.exception("broadcast_create_failed", created_by=created_by)
        await callback.message.edit_text("❌ Xatolik yuz berdi. Qayta urinib ko'ring.")
        await state.clear()
        return

    # Enqueue Celery worker
    try:
        process_broadcast_batch.delay(broadcast_id)
    except Exception:
        log.exception("broadcast_enqueue_failed", broadcast_id=broadcast_id)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Rassilka #{broadcast_id} navbatga qo'yildi!\n" "Jarayon fonda bajarilmoqda."
    )
    log.info("broadcast_enqueued", broadcast_id=broadcast_id, created_by=created_by)


@router.callback_query(
    F.message.chat.type == "private",
    StateFilter(
        BroadcastStates.choosing_segment,
        BroadcastStates.choosing_stage,
        BroadcastStates.choosing_payload,
        BroadcastStates.confirming,
    ),
    F.data == "bcast:cancel",
)
async def cb_cancel(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    await callback.answer()
    await _cancel_flow(callback, state)
    await callback.message.edit_text("❌ Rassilka bekor qilindi.")
