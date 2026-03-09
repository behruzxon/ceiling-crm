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
from infrastructure.di import get_tenant_menu_config
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

    # ── Deep links from group URL inline menu ───────────────────────────────
    if command.args == "zakaz":
        from apps.bot.handlers.private.order import cmd_order_start
        await state.clear()
        await cmd_order_start(message, state, **data)
        return

    if command.args == "price":
        from apps.bot.handlers.private.pricing import cmd_pricing_start
        await state.clear()
        await cmd_pricing_start(message, state, **data)
        return

    if command.args == "katalog":
        from apps.bot.handlers.private.catalog import cmd_catalog
        await state.clear()
        await cmd_catalog(message, state, **data)
        return

    if command.args == "paketlar":
        from apps.bot.handlers.private.packages import cmd_packages
        await state.clear()
        await cmd_packages(message, **data)
        return

    if command.args == "orders":
        from apps.bot.handlers.private.my_orders import cmd_my_orders
        await state.clear()
        await cmd_my_orders(message, **data)
        return

    if command.args == "operator":
        from apps.bot.handlers.private.operator import handle_operator_entry
        await state.clear()
        await handle_operator_entry(message, state, **data)
        return

    if command.args == "discounts":
        from apps.bot.handlers.private.promotions import cmd_promotions
        await state.clear()
        await cmd_promotions(message, **data)
        return

    if command.args == "ai":
        from apps.bot.handlers.private.ai_support import cmd_ai_start
        await state.clear()
        await cmd_ai_start(message, state, **data)
        return

    if command.args == "about":
        from apps.bot.handlers.private.about import cmd_about
        await state.clear()
        await cmd_about(message, **data)
        return

    # ── Normal /start ───────────────────────────────────────────────────────
    await state.clear()
    await clear_ai_conversation(user_id)
    log.info("start_private", chat_id=message.chat.id, chat_type=message.chat.type)

    db_user = data.get("db_user")
    db_session = data.get("db_session")
    user_role = data.get("user_role")

    # Load tenant for tenant-aware welcome
    tenant = None
    menu_config = None
    if db_user and db_session and getattr(db_user, "tenant_id", None):
        from infrastructure.database.models.tenant import TenantModel
        tenant = await db_session.get(TenantModel, db_user.tenant_id)
        if tenant:
            menu_config = tenant.menu_config or None

    # ── Auto-onboarding for tenantless users ─────────────────────────────
    # If user has no tenant and is not an admin of the platform bot,
    # check if they already own a tenant (admin_user_id) or offer onboarding.
    if tenant is None and not _is_bot_admin(user_id):
        from infrastructure.di import get_tenant_service as _get_tsvc
        if db_session:
            _tsvc = _get_tsvc(db_session)
            _existing = await _tsvc.get_by_admin_user(user_id)
            if _existing:
                # User owns a tenant but db_user.tenant_id not set yet
                tenant = _existing
                menu_config = _existing.menu_config or None
            else:
                # New user — start auto-onboarding
                from apps.bot.handlers.private.auto_onboarding import (
                    start_auto_onboarding,
                )
                await start_auto_onboarding(message, state)
                return

    # Determine owner status
    is_owner = False
    if tenant and tenant.admin_user_id == user_id:
        is_owner = True
    if user_role and hasattr(user_role, "value") and user_role.value in ("admin", "superadmin"):
        is_owner = True

    is_admin = _is_bot_admin(user_id) or is_owner
    first_name = message.from_user.first_name or ""

    # Build welcome text
    if tenant:
        from shared.templates.business_templates import get_welcome_text
        greeting = get_welcome_text(
            business_type=tenant.business_type,
            tenant_name=tenant.name,
            first_name=first_name,
            is_owner=is_owner,
        )
    else:
        # Default VashPotolok (backward compatible — platform admin sees this)
        greeting = (
            "\U0001f916 VashPotolok AI Bot\n\n"
            f"Assalomu alaykum, {first_name}! \U0001f44b\n"
            "VashPotolok kompaniyasining rasmiy AI yordamchisiga xush kelibsiz.\n\n"
            "Qashqadaryo bo\u02bbylab yuqori sifatli natijnoy potolok "
            "xizmatlarini taqdim etamiz.\n\n"
            "Siz bu yerda:\n"
            "\U0001f4b0 Potolok narxini aniq hisoblay olasiz\n"
            "\U0001f3a8 10+ turdagi dizayn variantlarini ko\u02bbrishingiz mumkin\n"
            "\U0001f4c2 Real loyihalar katalogini ko\u02bbrasiz\n"
            "\U0001f9d1\u200d\U0001f527 Buyurtma qoldirib operator bilan bog\u02bblanasiz\n"
            "\U0001f916 AI mutaxassis Madina 24/7 savollaringizga javob beradi\n\n"
            "\U0001f447 Boshlash uchun kerakli bo\u02bblimni tanlang"
        )
        if is_owner:
            from shared.templates.business_templates import OWNER_SECTION
            greeting += OWNER_SECTION

    await message.answer(
        greeting,
        reply_markup=main_menu_keyboard(is_admin=is_admin, menu_config=menu_config),
    )


@router.message(Command("menu"), F.chat.type == "private")
async def cmd_menu(message: Message, **data) -> None:
    """Show the main menu keyboard in a private chat."""
    user_id = message.from_user.id if message.from_user else 0
    db_user = data.get("db_user")
    db_session = data.get("db_session")
    menu_config = None
    if db_user and db_session:
        menu_config = await get_tenant_menu_config(db_session, db_user.tenant_id)
    await message.answer(
        "Menyu:",
        reply_markup=main_menu_keyboard(
            is_admin=_is_bot_admin(user_id), menu_config=menu_config,
        ),
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
    db_user = data.get("db_user")
    db_session = data.get("db_session")
    menu_config = None
    if db_user and db_session:
        menu_config = await get_tenant_menu_config(db_session, db_user.tenant_id)
    await message.answer(
        "❎ Amal bekor qilindi.",
        reply_markup=main_menu_keyboard(
            is_admin=_is_bot_admin(user_id), menu_config=menu_config,
        ),
    )
