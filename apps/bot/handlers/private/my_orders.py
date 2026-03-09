"""
apps.bot.handlers.private.my_orders
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"📦 Buyurtmalarim" submenu — works in private and group chats.

Submenu buttons
---------------
  📊 Mening buyurtmalarim  — last 5 orders with pipeline stage
  📦 Buyurtma holati       — latest order stage + next-step hint
  🧾 Hisob-kitob tarixi    — last 10 payments across all user orders
  🛠 Kafolat ma'lumoti     — warranty card for latest completed order
  ⬅️ Orqaga                — return to main menu
"""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from apps.bot.keyboards.main_menu import main_menu_keyboard
from apps.bot.keyboards.my_orders import my_orders_keyboard
from infrastructure.di import (
    get_lead_repo,
    get_payment_service,
    get_warranty_service,
)
from shared.constants.enums import PaymentMethod, PaymentStatus, PipelineStage
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:my_orders")


# ── Stage display strings ─────────────────────────────────────────────────────

_STAGE_EMOJI: dict[PipelineStage, str] = {
    PipelineStage.NEW:          "🟡",
    PipelineStage.CONTACTED:    "⚪️",
    PipelineStage.MEASUREMENT:  "🟠",
    PipelineStage.QUOTE:        "🟣",
    PipelineStage.DEAL:         "🔵",
    PipelineStage.INSTALLATION: "🟢",
    PipelineStage.COMPLETED:    "✅",
    PipelineStage.LOST:         "🔴",
}

_STAGE_NAME: dict[PipelineStage, str] = {
    PipelineStage.NEW:          "Yangi",
    PipelineStage.CONTACTED:    "Bog'landi",
    PipelineStage.MEASUREMENT:  "O'lchov",
    PipelineStage.QUOTE:        "Taklif",
    PipelineStage.DEAL:         "Buyurtma berildi",
    PipelineStage.INSTALLATION: "O'rnatildi",
    PipelineStage.COMPLETED:    "Yakunlandi",
    PipelineStage.LOST:         "Bekor qilindi",
}

_STAGE_HINTS: dict[PipelineStage, str] = {
    PipelineStage.NEW:          "Menejer tez orada bog'lanadi.",
    PipelineStage.CONTACTED:    "O'lchov vaqti kelishiladi.",
    PipelineStage.MEASUREMENT:  "O'lchov vaqti kelishiladi.",
    PipelineStage.QUOTE:        "Narx tasdiqlansa, buyurtma boshlanadi.",
    PipelineStage.DEAL:         "Montaj rejalashtirilmoqda.",
    PipelineStage.INSTALLATION: "Tekshiruv va kafolat rasmiylashadi.",
    PipelineStage.COMPLETED:    "Rahmat! Kafolat amal qiladi.",
    PipelineStage.LOST:         "Bekor qilingan. Yangi buyurtma berishingiz mumkin.",
}


def _stage_badge(stage: PipelineStage) -> str:
    """Return a formatted stage badge line: 📌 Holat: <emoji> <name>"""
    emoji = _STAGE_EMOJI.get(stage, "⚪️")
    name = _STAGE_NAME.get(stage, stage.value)
    return f"📌 Holat: {emoji} {name}"


# ── Category display labels ───────────────────────────────────────────────────

_CATEGORY_LABELS: dict[str, str] = {
    "gulli":         "🌸 Gulli",
    "odnotonny":     "🎨 Odnotonny",
    "mramor":        "🪨 Mramor",
    "qora_naqsh_uf": "🖤 Qora naqsh (UF)",
    "hi_tech":       "✨ Hi-tech",
    "kosmos":        "🌌 Kosmos",
    "osmon":         "☁️ Osmon",
    "oshxona":       "🍳 Oshxona",
    "naqsh_ramka":   "🖼 Naqsh ramka",
    "naqsh_oq":      "💎 Naqsh oq",
}

_METHOD_LABELS: dict[PaymentMethod, str] = {
    PaymentMethod.CASH:     "Naqd",
    PaymentMethod.CARD:     "Karta",
    PaymentMethod.TRANSFER: "O'tkazma",
}

_STATUS_LABELS: dict[PaymentStatus, str] = {
    PaymentStatus.PENDING:  "Kutilmoqda",
    PaymentStatus.PAID:     "To'landi ✅",
    PaymentStatus.CANCELED: "Bekor",
    PaymentStatus.REFUNDED: "Qaytarildi",
}

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ── Entry: show submenu ────────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == "📦 Buyurtmalarim")
async def cmd_my_orders(message: Message, **data: object) -> None:
    await message.answer(
        "📦 <b>Buyurtmalarim</b>\n\nKerakli bo'limni tanlang:",
        reply_markup=my_orders_keyboard(),
    )


# ── 📊 Mening buyurtmalarim ───────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == "📊 Mening buyurtmalarim")
async def cmd_orders_list(message: Message, **data: object) -> None:
    user_id: int = message.from_user.id if message.from_user else 0
    _tid = data.get("tenant_id")
    db_session: AsyncSession = data["db_session"]  # type: ignore[assignment]
    lead_repo = get_lead_repo(db_session, tenant_id=_tid)
    leads = await lead_repo.list_by_user(user_id, limit=5)

    if not leads:
        await message.answer(
            "📭 Sizda hali buyurtma yo'q.\n\n"
            "Yangi buyurtma berish uchun «✅ Zakaz berish» tugmasini bosing.",
            reply_markup=my_orders_keyboard(),
        )
        return

    cards: list[str] = []
    for lead in leads:
        date_str = lead.created_at.strftime("%d.%m.%Y") if lead.created_at else "—"
        category_label = _CATEGORY_LABELS.get(lead.category.value, lead.category.value)
        lines = [
            f"📦 <b>#{lead.id}</b> | {date_str}",
            f"📍 {lead.district or '—'}",
            f"🎨 {category_label}",
        ]
        if lead.room_area:
            lines.append(f"📐 {lead.room_area} m²")
        lines.append(_stage_badge(lead.current_stage))
        cards.append("\n".join(lines))

    header = "📋 <b>So'nggi buyurtmalaringiz:</b>"
    await message.answer(
        header + "\n\n" + "\n\n".join(cards),
        reply_markup=my_orders_keyboard(),
    )


# ── 📦 Buyurtma holati ────────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == "📦 Buyurtma holati")
async def cmd_order_status(message: Message, **data: object) -> None:
    user_id: int = message.from_user.id if message.from_user else 0
    _tid = data.get("tenant_id")
    db_session: AsyncSession = data["db_session"]  # type: ignore[assignment]
    lead_repo = get_lead_repo(db_session, tenant_id=_tid)
    leads = await lead_repo.list_by_user(user_id, limit=1)

    if not leads:
        await message.answer(
            "📭 Hali buyurtma yo'q.",
            reply_markup=my_orders_keyboard(),
        )
        return

    lead = leads[0]
    hint = _STAGE_HINTS.get(lead.current_stage, "")

    await message.answer(
        f"📦 <b>Oxirgi buyurtma</b>\n"
        f"📍 {lead.district or '—'}\n"
        f"{_stage_badge(lead.current_stage)}\n"
        f"➡️ <i>{hint}</i>",
        reply_markup=my_orders_keyboard(),
    )


# ── 🧾 Hisob-kitob tarixi ─────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == "🧾 Hisob-kitob tarixi")
async def cmd_payment_history(message: Message, **data: object) -> None:
    user_id: int = message.from_user.id if message.from_user else 0
    _tid = data.get("tenant_id")
    db_session: AsyncSession = data["db_session"]  # type: ignore[assignment]
    lead_repo = get_lead_repo(db_session, tenant_id=_tid)
    payment_service = get_payment_service(db_session, tenant_id=_tid)

    leads = await lead_repo.list_by_user(user_id, limit=5)
    if not leads:
        await message.answer(
            "📭 Hali to'lov yo'q.",
            reply_markup=my_orders_keyboard(),
        )
        return

    all_payments = []
    for lead in leads:
        payments = await payment_service.list_by_lead(lead.id)
        all_payments.extend(payments)

    if not all_payments:
        await message.answer(
            "📭 Hali to'lov yo'q.",
            reply_markup=my_orders_keyboard(),
        )
        return

    # Sort newest first, take 10
    all_payments.sort(
        key=lambda p: p.paid_at or p.created_at or _EPOCH,
        reverse=True,
    )
    recent = all_payments[:10]

    lines: list[str] = ["🧾 <b>To'lov tarixi:</b>\n"]
    for p in recent:
        ref_dt = p.paid_at or p.created_at
        date_str = ref_dt.strftime("%d.%m.%Y") if ref_dt else "—"
        method = _METHOD_LABELS.get(p.method, p.method.value)
        status = _STATUS_LABELS.get(p.status, p.status.value)
        amount_fmt = f"{p.amount:,}".replace(",", "\u00a0")
        lines.append(
            f"• {date_str}  <b>{amount_fmt} so'm</b>\n"
            f"  {method} | {status} | #{p.lead_id}"
        )

    await message.answer("\n\n".join(lines), reply_markup=my_orders_keyboard())


# ── 🛠 Kafolat ma'lumoti ──────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == "🛠 Kafolat ma'lumoti")
async def cmd_warranty_info(message: Message, **data: object) -> None:
    user_id: int = message.from_user.id if message.from_user else 0
    _tid = data.get("tenant_id")
    db_session: AsyncSession = data["db_session"]  # type: ignore[assignment]
    lead_repo = get_lead_repo(db_session, tenant_id=_tid)
    warranty_service = get_warranty_service(db_session, tenant_id=_tid)

    leads = await lead_repo.list_by_user(user_id, limit=5)
    if not leads:
        await message.answer(
            "📭 Hali buyurtma yo'q.",
            reply_markup=my_orders_keyboard(),
        )
        return

    # Check leads newest-first for a warranty; use the first found
    warranty = None
    for lead in leads:
        warranty = await warranty_service.get_by_lead(lead.id)
        if warranty:
            break

    if warranty is None:
        await message.answer(
            "🛠 <b>Kafolat ma'lumoti</b>\n\n"
            "Kafolat hali berilmagan.\n"
            "<i>Kafolat o'rnatish ishlari tugagandan so'ng rasmiylashtiladi.</i>",
            reply_markup=my_orders_keyboard(),
        )
        return

    card_no = warranty.warranty_card_no or "—"
    await message.answer(
        f"🛡 <b>Kafolat ma'lumoti</b>\n\n"
        f"📋 Raqam: <code>{card_no}</code>\n"
        f"📅 Berilgan: {warranty.issued_at.strftime('%d.%m.%Y')}\n"
        f"⏳ Amal qiladi: {warranty.expires_at.strftime('%d.%m.%Y')}\n"
        f"🔖 Buyurtma: #{warranty.lead_id}",
        reply_markup=my_orders_keyboard(),
    )


# ── ⬅️ Orqaga ─────────────────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == "⬅️ Orqaga")
async def cmd_back_to_main(message: Message, **data: object) -> None:
    await message.answer(
        "🏠 Asosiy menyu:",
        reply_markup=main_menu_keyboard(),
    )
