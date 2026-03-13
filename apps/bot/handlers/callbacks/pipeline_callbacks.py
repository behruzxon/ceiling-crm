"""
Pipeline stage transition callbacks.

Handlers:
  pipeline:advance:{id}          — show valid-next-stages menu (legacy, kept)
  pipeline:do_advance:{id}:{st}  — execute explicit stage pick (legacy, kept)
  pipeline:next:{id}             — advance to next natural stage directly
  pipeline:prev:{id}             — go back to previous natural stage
  pipeline:lost:{id}             — show LOST reason inline keyboard
  pipeline:lost_confirm:{id}:{r} — mark LOST with preset reason
  pipeline:lost_other:{id}       — enter FSM to collect custom reason text
  timeline:{id}                  — show last 20 actions for a lead
  stage_page:{stage}:{page}      — paginate /stage results

  Message(PipelineStates.waiting_lost_reason)
                                 — collect custom LOST reason text
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.handlers.admin.pipeline import (
    ACTION_EMOJI,
    STAGE_EMOJI,
    _summarize_payload,
)
from apps.bot.states.pipeline import PipelineStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_crm_service, get_lead_action_repo, get_lead_repo
from shared.constants.enums import PipelineStage
from shared.exceptions.base import (
    InvalidStageTransitionError,
    MissingLostReasonError,
    NotFoundError,
)
from shared.utils.formatting import bold

router = Router(name="callbacks:pipeline")

_TZ = ZoneInfo("Asia/Tashkent")

# Natural linear order used by Next / Prev stage buttons.
# PACKAGE_SELECTED is an entry-point stage (not in the linear progression).
_LINEAR_ORDER: list[PipelineStage] = [
    PipelineStage.NEW,
    PipelineStage.CONTACTED,
    PipelineStage.MEASUREMENT,
    PipelineStage.QUOTE,
    PipelineStage.DEAL,
    PipelineStage.INSTALLATION,
    PipelineStage.COMPLETED,
]

# Preset LOST reasons
_LOST_REASONS: list[tuple[str, str]] = [
    ("no_budget",   "💸 Byudjet yo'q"),
    ("competitor",  "🏪 Raqobatchi tanladi"),
    ("no_answer",   "📵 Javob yo'q"),
    ("postponed",   "⏳ Kechiktirildi"),
]
_LOST_REASON_TEXT: dict[str, str] = {
    "no_budget":  "Byudjet yo'q",
    "competitor": "Raqobatchi tanladi",
    "no_answer":  "Javob yo'q",
    "postponed":  "Kechiktirildi",
}


def _current_idx(stage: PipelineStage) -> int:
    """Index of *stage* in _LINEAR_ORDER, or 0 for non-linear stages."""
    try:
        return _LINEAR_ORDER.index(stage)
    except ValueError:
        return 0


async def _log_stage_action(
    session: object,
    lead_id: int,
    actor_id: int,
    old_stage: PipelineStage,
    new_stage: PipelineStage,
    extra: dict | None = None,  # type: ignore[type-arg]
) -> None:
    """Insert the right action_type based on which stage we moved to."""
    if new_stage == PipelineStage.MEASUREMENT:
        action = "measurement_set"
    elif new_stage == PipelineStage.COMPLETED:
        action = "order_done"
    else:
        action = "status_changed"

    payload: dict = {"old": old_stage.value, "new": new_stage.value}  # type: ignore[type-arg]
    if extra:
        payload.update(extra)

    await get_lead_action_repo(session).insert(lead_id, actor_id, action, payload=payload)  # type: ignore[arg-type]


# ── Legacy: show menu of valid next stages ────────────────────────────────────

@router.callback_query(F.data.startswith("pipeline:advance:"))
async def cb_advance_stage(callback: CallbackQuery, **data: object) -> None:
    """Show valid next stages for the lead (legacy menu approach)."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        crm = get_crm_service(session)
        lead_repo = get_lead_repo(session)

        lead = await lead_repo.get_by_id(lead_id)
        if lead is None:
            await callback.answer("Lid topilmadi", show_alert=True)
            return

        valid_next = crm.get_valid_transitions(lead.current_stage)
        if not valid_next:
            await callback.answer("Bu bosqichdan o'tish mumkin emas", show_alert=True)
            return

        buttons = [
            [InlineKeyboardButton(
                text=f"{STAGE_EMOJI.get(stage, '▪️')} {stage.value}",
                callback_data=f"pipeline:do_advance:{lead_id}:{stage.value}",
            )]
            for stage in valid_next
            if stage != PipelineStage.LOST
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(  # type: ignore[union-attr]
            f"📊 Lid #{lead_id}\n"
            f"Hozirgi: {bold(lead.current_stage.value)}\n\n"
            "Keyingi bosqichni tanlang:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(F.data.startswith("pipeline:do_advance:"))
async def cb_do_advance(callback: CallbackQuery, **data: object) -> None:
    """Execute a stage transition chosen from the legacy menu."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    lead_id = int(parts[2])
    new_stage = PipelineStage(parts[3])
    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            crm = get_crm_service(session)
            lead = await get_lead_repo(session).get_by_id(lead_id)
            old_stage = lead.current_stage if lead else PipelineStage.NEW

            await crm.advance_stage(lead_id, new_stage, actor_id)
            await _log_stage_action(session, lead_id, actor_id, old_stage, new_stage)
            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"✅ Lid #{lead_id} → {bold(new_stage.value)}\n"
                f"/lead_{lead_id} — karta ko'rish"
            )
            await callback.answer("Bosqich o'zgartirildi!")
        except InvalidStageTransitionError as e:
            await callback.answer(str(e), show_alert=True)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise


# ── Next natural stage ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pipeline:next:"))
async def cb_next_stage(callback: CallbackQuery, **data: object) -> None:
    """Directly advance to the next stage in the natural pipeline order."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return
    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        lead = await get_lead_repo(session).get_by_id(lead_id)
        if lead is None:
            await callback.answer("Lid topilmadi", show_alert=True)
            return

        current = lead.current_stage
        idx = _current_idx(current)

        if idx >= len(_LINEAR_ORDER) - 1:
            await callback.answer("Bu oxirgi bosqich ✅", show_alert=True)
            return

        new_stage = _LINEAR_ORDER[idx + 1]

        try:
            crm = get_crm_service(session)
            await crm.advance_stage(lead_id, new_stage, actor_id)
            await _log_stage_action(session, lead_id, actor_id, current, new_stage)
            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"➡️ Lid #{lead_id}: {current.value} → {bold(new_stage.value)}\n"
                f"/lead_{lead_id} — yangilangan karta"
            )
            await callback.answer(f"→ {new_stage.value}")
        except InvalidStageTransitionError as e:
            await callback.answer(str(e), show_alert=True)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise


# ── Prev natural stage ────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pipeline:prev:"))
async def cb_prev_stage(callback: CallbackQuery, **data: object) -> None:
    """Go back one step in the natural pipeline order (undo / correction)."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return
    actor_id = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        lead = await get_lead_repo(session).get_by_id(lead_id)
        if lead is None:
            await callback.answer("Lid topilmadi", show_alert=True)
            return

        current = lead.current_stage

        if current == PipelineStage.LOST:
            await callback.answer(
                "LOST bosqichini qaytarish uchun /lead_N orqali yangi bosqich tanlang",
                show_alert=True,
            )
            return

        idx = _current_idx(current)
        if idx == 0:
            await callback.answer("Bu birinchi bosqich — orqaga qaytib bo'lmaydi", show_alert=True)
            return

        prev_stage = _LINEAR_ORDER[idx - 1]

        try:
            crm = get_crm_service(session)
            await crm.advance_stage(
                lead_id, prev_stage, actor_id,
                note=f"Qaytarildi ({current.value} → {prev_stage.value})",
            )
            await _log_stage_action(
                session, lead_id, actor_id, current, prev_stage,
                extra={"reason": "undo"},
            )
            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"⬅️ Lid #{lead_id}: {current.value} → {bold(prev_stage.value)}\n"
                f"/lead_{lead_id} — yangilangan karta"
            )
            await callback.answer(f"← {prev_stage.value}")
        except InvalidStageTransitionError as e:
            await callback.answer(str(e), show_alert=True)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise


# ── LOST: show reason picker ──────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^pipeline:lost:\d+$"))
async def cb_mark_lost(callback: CallbackQuery, **data: object) -> None:
    """Show the LOST reason selection keyboard."""
    lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]

    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"pipeline:lost_confirm:{lead_id}:{slug}",
        )]
        for slug, label in _LOST_REASONS
    ]
    buttons.append([InlineKeyboardButton(
        text="✏️ Boshqa...",
        callback_data=f"pipeline:lost_other:{lead_id}",
    )])

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"❌ Lid #{lead_id} — Yo'qotish sababini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ── LOST: preset reason confirmed ────────────────────────────────────────────

@router.callback_query(F.data.startswith("pipeline:lost_confirm:"))
async def cb_lost_confirm(callback: CallbackQuery, **data: object) -> None:
    """Mark lead as LOST with a preset reason."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    lead_id = int(parts[2])
    reason_slug = parts[3]
    actor_id = callback.from_user.id  # type: ignore[union-attr]
    reason_text = _LOST_REASON_TEXT.get(reason_slug, reason_slug)

    factory = get_session_factory()
    async with factory() as session:
        try:
            crm = get_crm_service(session)
            await crm.advance_stage(
                lead_id, PipelineStage.LOST, actor_id, note=reason_text
            )
            await get_lead_action_repo(session).insert(
                lead_id, actor_id, "status_changed",
                payload={"new": PipelineStage.LOST.value, "reason": reason_text},
            )
            # Persist lost_reason on the lead row for analytics
            lead_repo = get_lead_repo(session)
            await lead_repo.set_lost_reason(lead_id, reason_text)
            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"❌ Lid #{lead_id} yo'qotildi\n"
                f"Sabab: {bold(reason_text)}"
            )
            await callback.answer("Lid yo'qotildi deb belgilandi")
        except InvalidStageTransitionError as e:
            await callback.answer(str(e), show_alert=True)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise


# ── LOST: other (free-text) — enter FSM ──────────────────────────────────────

@router.callback_query(F.data.startswith("pipeline:lost_other:"))
async def cb_lost_other(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Set FSM state to collect a custom LOST reason text."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    await state.set_state(PipelineStates.waiting_lost_reason)
    await state.update_data(lost_lead_id=lead_id)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✏️ Lid #{lead_id} — Yo'qotish sababini yozing (xabar yuboring):"
    )
    await callback.answer()


@router.message(PipelineStates.waiting_lost_reason)
async def handle_lost_reason_text(message: Message, state: FSMContext, **data: object) -> None:
    """Receive custom LOST reason text, then mark the lead LOST."""
    if not message.text:
        await message.answer("Iltimos, matn ko'rinishida sabab yozing")
        return

    reason_text = message.text.strip()
    if not reason_text:
        await message.answer("Sabab bo'sh bo'lishi mumkin emas")
        return

    state_data = await state.get_data()
    lead_id: int | None = state_data.get("lost_lead_id")
    if lead_id is None:
        await state.clear()
        await message.answer("Xatolik: lid ID topilmadi. Iltimos, qaytadan urining.")
        return

    actor_id = message.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            crm = get_crm_service(session)
            await crm.advance_stage(
                lead_id, PipelineStage.LOST, actor_id, note=reason_text
            )
            await get_lead_action_repo(session).insert(
                lead_id, actor_id, "status_changed",
                payload={"new": PipelineStage.LOST.value, "reason": reason_text},
            )
            # Persist lost_reason on the lead row for analytics
            lead_repo = get_lead_repo(session)
            await lead_repo.set_lost_reason(lead_id, reason_text)
            await session.commit()
            await state.clear()

            await message.answer(
                f"❌ Lid #{lead_id} yo'qotildi\n"
                f"Sabab: {bold(reason_text)}"
            )
        except (InvalidStageTransitionError, MissingLostReasonError) as e:
            await state.clear()
            await message.answer(f"Bosqich o'zgartirib bo'lmaydi: {e}")
        except NotFoundError:
            await state.clear()
            await message.answer(f"Lid #{lead_id} topilmadi")
        except Exception:
            await session.rollback()
            await state.clear()
            await message.answer("Xatolik yuz berdi")
            raise


# ── Timeline callback ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("timeline:"))
async def cb_timeline(callback: CallbackQuery, **data: object) -> None:
    """Show last 20 actions for a lead as a chronological timeline."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        action_repo = get_lead_action_repo(session)
        actions = await action_repo.get_lead_timeline(lead_id, limit=20)

    if not actions:
        await callback.answer("Harakatlar tarixi yo'q", show_alert=True)
        return

    lines = [f"📈 {bold(f'Lid #{lead_id}')} — Timeline:\n"]
    for act in reversed(actions):  # oldest → newest
        dt = act["created_at"].astimezone(_TZ).strftime("%d.%m %H:%M")
        emoji = ACTION_EMOJI.get(act["action_type"], "▪️")
        actor_name = act.get("first_name") or f"#{act['actor_user_id']}"
        username = act.get("username")
        actor_str = f"{actor_name} (@{username})" if username else actor_name
        payload_str = ""
        if act.get("payload"):
            payload_str = f" — {_summarize_payload(act['payload'])}"
        lines.append(
            f"{emoji} [{dt}] {act['action_type']} — {actor_str}{payload_str}"
        )

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…"

    # Send as new message (timeline is long, editing the card is not ideal)
    await callback.message.answer(text)  # type: ignore[union-attr]
    await callback.answer()


# ── Stage pagination callback ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("stage_page:"))
async def cb_stage_page(callback: CallbackQuery, **data: object) -> None:
    """Paginate through leads in a pipeline stage."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    # callback_data format: stage_page:{STAGE_VALUE}:{page_index}
    try:
        stage_str = parts[1]
        page = int(parts[2])
        stage = PipelineStage(stage_str)
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    page_size = 10
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session)
        leads = await lead_repo.search(
            stage=stage,
            limit=page_size + 1,
            offset=page * page_size,
        )

    has_more = len(leads) > page_size
    leads = leads[:page_size]

    if not leads:
        await callback.answer("Boshqa lid yo'q", show_alert=True)
        return

    emoji = STAGE_EMOJI.get(stage, "▪️")
    lines = [f"{emoji} {bold(stage.value)} — sahifa {page + 1}\n"]
    for i, lead in enumerate(leads, start=page * page_size + 1):
        status_tag = f" [{lead.lead_status}]" if lead.lead_status else ""
        dt = lead.created_at.astimezone(_TZ).strftime("%d.%m %H:%M")
        lines.append(
            f"{i}. {bold(f'#{lead.id}')} {lead.name} · {lead.district}{status_tag}\n"
            f"   📱 {lead.phone} · {dt} · /lead_{lead.id}"
        )

    row = []
    if page > 0:
        row.append(InlineKeyboardButton(
            text="◀️ Oldingi",
            callback_data=f"stage_page:{stage.value}:{page - 1}",
        ))
    if has_more:
        row.append(InlineKeyboardButton(
            text="▶️ Keyingi",
            callback_data=f"stage_page:{stage.value}:{page + 1}",
        ))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[row]) if row else None

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=keyboard,
    )
    await callback.answer()
