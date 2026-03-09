"""
apps.bot.handlers.private.payment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manual payment submission FSM — private chats only.

Flow
----
  User taps "💳 To'lov qilish"
    └─► Show requisites + ask for amount   [waiting_amount]
          └─► User sends integer amount
                └─► Ask for receipt proof  [waiting_proof]
                      └─► User sends photo OR document
                            └─► Create PENDING payment, notify admin, confirm user

Admin receives a photo/document message with [✅ Tasdiqlash] [❌ Rad etish] buttons.
Those callbacks are handled in apps.bot.handlers.callbacks.payment_callbacks.
"""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from sqlalchemy.ext.asyncio import AsyncSession

from apps.bot.keyboards.my_orders import my_orders_keyboard
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo, get_payment_service
from shared.config import get_settings
from shared.constants.enums import PaymentMethod
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:payment")


# ── FSM ──────────────────────────────────────────────────────────────────────

class PaymentSubmitFSM(StatesGroup):
    waiting_amount = State()
    waiting_proof  = State()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_card(number: str | None) -> str:
    """Format raw digit string as '8600 1234 5678 1234'."""
    if not number:
        return "—"
    clean = "".join(c for c in number if c.isdigit())
    return " ".join(clean[i : i + 4] for i in range(0, len(clean), 4)) or "—"


async def _notify_admin(
    bot: Bot,
    *,
    payment_id: int,
    lead_id: int,
    user_id: int,
    amount: int,
    file_id: str,
    is_photo: bool,
) -> None:
    """Send payment receipt to admin DM with approve/reject inline buttons."""
    admin_user_id = get_settings().bot.admin_user_id
    if not admin_user_id:
        log.warning("admin_user_id_not_set_skipping_payment_notify", payment_id=payment_id)
        return

    amount_fmt = f"{amount:,}".replace(",", "\u00a0")
    caption = (
        f"💳 <b>Yangi to'lov (PENDING)</b>\n"
        f"Lead #{lead_id}\n"
        f"User ID: <code>{user_id}</code>\n"
        f"Summa: <b>{amount_fmt} so'm</b>"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="✅ Tasdiqlash",
                callback_data=f"pay:a:{payment_id}:{user_id}",
            ),
            InlineKeyboardButton(
                text="❌ Rad etish",
                callback_data=f"pay:r:{payment_id}:{user_id}",
            ),
        ]]
    )

    try:
        if is_photo:
            await bot.send_photo(
                chat_id=admin_user_id,
                photo=file_id,
                caption=caption,
                reply_markup=keyboard,
            )
        else:
            await bot.send_document(
                chat_id=admin_user_id,
                document=file_id,
                caption=caption,
                reply_markup=keyboard,
            )
        log.info("payment_admin_notified", payment_id=payment_id, admin=admin_user_id)
    except Exception:
        log.exception("payment_admin_notify_failed", payment_id=payment_id)


# ── Entry: show requisites + ask amount ──────────────────────────────────────

@router.message(F.chat.type == "private", F.text == "💳 To'lov qilish")
async def cmd_payment_start(message: Message, state: FSMContext, **data: object) -> None:
    user_id: int = message.from_user.id if message.from_user else 0
    _tid = data.get("tenant_id")
    db_session: AsyncSession = data["db_session"]  # type: ignore[assignment]
    lead_repo = get_lead_repo(db_session, tenant_id=_tid)
    leads = await lead_repo.list_by_user(user_id, limit=1)

    if not leads:
        await message.answer(
            "📭 Hali buyurtma yo'q.\n"
            "Avval buyurtma bering.",
            reply_markup=my_orders_keyboard(),
        )
        return

    await state.clear()
    await state.set_data({"lead_id": leads[0].id, "_tenant_id": _tid})
    await state.set_state(PaymentSubmitFSM.waiting_amount)

    ps = get_settings().payment
    card_fmt = _fmt_card(ps.card_number)
    holder = ps.card_holder or "—"
    bank = ps.bank_name or "—"

    await message.answer(
        f"💳 <b>To'lov uchun rekvizit:</b>\n\n"
        f"Karta: <code>{card_fmt}</code>\n"
        f"Ism: <b>{holder}</b>\n"
        f"Bank: <b>{bank}</b>\n\n"
        "To'lov qilgach, summa kiriting (so'm):",
        reply_markup=ReplyKeyboardRemove(),
    )


# ── Step 1: amount ────────────────────────────────────────────────────────────

@router.message(StateFilter(PaymentSubmitFSM.waiting_amount), F.text, ~F.text.startswith("/"))
async def handle_payment_amount(message: Message, state: FSMContext, **data: object) -> None:
    raw = (message.text or "").strip().replace(" ", "").replace(",", "")
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer("❌ Faqat musbat son kiriting (so'm):")
        return

    await state.update_data(amount=int(raw))
    await state.set_state(PaymentSubmitFSM.waiting_proof)
    await message.answer("📎 Chek rasmini yoki PDF yuboring.")


# ── Step 2a: proof — photo ─────────────────────────────────────────────────────

@router.message(StateFilter(PaymentSubmitFSM.waiting_proof), F.photo)
async def handle_payment_proof_photo(message: Message, state: FSMContext, **data: object) -> None:
    # Telegram provides photos sorted by size; last = highest resolution
    file_id = message.photo[-1].file_id
    await _save_and_confirm(message, state, file_id=file_id, is_photo=True)


# ── Step 2b: proof — document ─────────────────────────────────────────────────

@router.message(StateFilter(PaymentSubmitFSM.waiting_proof), F.document)
async def handle_payment_proof_document(message: Message, state: FSMContext, **data: object) -> None:
    if not message.document:
        await message.answer("❌ Fayl topilmadi. Qayta yuboring:")
        return
    file_id = message.document.file_id
    await _save_and_confirm(message, state, file_id=file_id, is_photo=False)


# ── Step 2 fallback ───────────────────────────────────────────────────────────

@router.message(StateFilter(PaymentSubmitFSM.waiting_proof))
async def handle_payment_proof_fallback(message: Message, **data: object) -> None:
    await message.answer("📎 Iltimos, chek rasmini yoki PDF yuboring.")


# ── Shared: persist + notify ──────────────────────────────────────────────────

async def _save_and_confirm(
    message: Message,
    state: FSMContext,
    *,
    file_id: str,
    is_photo: bool,
) -> None:
    fsm = await state.get_data()
    _tid = fsm.get("_tenant_id")
    lead_id: int = fsm["lead_id"]
    amount: int = fsm["amount"]
    user_id: int = message.from_user.id if message.from_user else 0

    await state.clear()

    payment_id: int | None = None
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = get_payment_service(session, tenant_id=_tid)
            payment = await svc.create_payment(
                lead_id=lead_id,
                amount=amount,
                method=PaymentMethod.MANUAL,
                proof_file_id=file_id,
                notes="Bot orqali yuborilgan to'lov",
                created_by=user_id,
            )
            await session.commit()
        payment_id = payment.id
        log.info("payment_submitted", payment_id=payment_id, user_id=user_id, lead_id=lead_id)
    except Exception:
        log.exception("payment_submit_failed", user_id=user_id, lead_id=lead_id)

    await message.answer(
        "✅ Qabul qilindi. Tasdiqlangach xabar beramiz.",
        reply_markup=my_orders_keyboard(),
    )

    if payment_id and message.bot:
        await _notify_admin(
            message.bot,
            payment_id=payment_id,
            lead_id=lead_id,
            user_id=user_id,
            amount=amount,
            file_id=file_id,
            is_photo=is_photo,
        )
