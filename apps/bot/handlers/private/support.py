"""
AI support handler.
Routes ceiling-related questions to OpenAI with guardrails.
"""
from __future__ import annotations
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.handlers.private.ai_support import clear_ai_conversation
from apps.bot.keyboards.main_menu import main_menu_keyboard
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:support")


def _is_bot_admin(user_id: int) -> bool:
    settings = get_settings()
    return (
        settings.bot.admin_user_id is not None
        and user_id == settings.bot.admin_user_id
    )

HELP_TEXT = (
    "🏠 <b>Ceiling CRM Bot</b>\n\n"
    "Mavjud buyruqlar:\n"
    "/start — Botni ishga tushirish\n"
    "/catalog — Patalok katalogi\n"
    "/price — Narxni hisoblash\n"
    "/order — Buyurtma berish\n"
    "/help — Yordam\n"
    "/cancel — Amalni bekor qilish\n\n"
    "Savolingiz bo'lsa, shunchaki yozing — biz yordam beramiz!"
)


@router.message(Command("start"), F.chat.type == "private")
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, **data) -> None:
    """Clear FSM state and AI conversation thread, then greet (private only).

    Handles deep-link payload: ``/start share_phone`` → skip greeting and
    go straight to the phone-number request (operator callback flow).

    User profile data (lead stage, phone, design interests, dimensions)
    is intentionally preserved — only the active conversation thread is reset.
    Group /start is handled by group:start router.
    """
    user_id = message.from_user.id if message.from_user else 0

    # ── Deep link: share_phone ──────────────────────────────────────────────
    if command.args == "share_phone":
        from apps.bot.handlers.private.operator import OperatorFlow, _contact_keyboard
        await state.clear()
        await state.set_state(OperatorFlow.waiting_for_contact)
        await message.answer(
            "📲 Quyidagi tugmani bosib raqamingizni yuboring.\n\n"
            "<i>Namuna: +998 90 123 45 67</i>",
            reply_markup=_contact_keyboard(is_private=True),
        )
        log.info("start_share_phone", user_id=user_id)
        return

    # ── Normal /start ───────────────────────────────────────────────────────
    await state.clear()
    await clear_ai_conversation(user_id)
    log.info("start_private", chat_id=message.chat.id, chat_type=message.chat.type)
    await message.answer(
        f"Assalomu alaykum, {message.from_user.first_name}! 👋\n\n"
        "VashPotolok kompaniyasining rasmiy Potolok X botiga xush kelibsiz.\n\n"
        "Biz Qashqadaryo bo'ylab yuqori sifatli natijoy potolok xizmatini taqdim etamiz.\n"
        "Professional yondashuv va 15 yilgacha kafolat bilan.\n\n"
        "• 📐 Aniq narx hisoblash\n"
        "• 🎨 10+ turdagi dizayn\n"
        "• 📂 Real loyihalar katalogi\n"
        "• 📞 Tezkor operator aloqasi\n\n"
        "👇 Quyidagi bo'limlardan birini tanlang:",
        reply_markup=main_menu_keyboard(is_admin=_is_bot_admin(user_id)),
    )


@router.message(Command("menu"), F.chat.type == "private")
async def cmd_menu(message: Message, **data) -> None:
    """Show the main menu keyboard in a private chat."""
    user_id = message.from_user.id if message.from_user else 0
    await message.answer(
        "Menyu:",
        reply_markup=main_menu_keyboard(is_admin=_is_bot_admin(user_id)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, **data) -> None:
    """Clear any active FSM state, then show help menu."""
    await state.clear()
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext, **data) -> None:
    """Cancel any in-progress flow, clear FSM state, and return to main menu."""
    await state.clear()
    user_id = message.from_user.id if message.from_user else 0
    await message.answer(
        "❎ Amal bekor qilindi.",
        reply_markup=main_menu_keyboard(is_admin=_is_bot_admin(user_id)),
    )
