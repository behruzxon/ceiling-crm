"""
apps.bot.handlers.private.tenant_bot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tenant owner bot connection management.

Entry points:
  /connect_bot   -- start bot connection FSM flow
  /bot_status    -- show current bot connection status
  /disconnect_bot -- disconnect tenant bot

All inline callbacks use the ``tbot:`` prefix.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.states.tenant_bot import (
    TenantBotConnectStates,
    TenantBotReconnectStates,
)
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_tenant_bot_service, get_tenant_service
from shared.logging import get_logger
from shared.utils.validators import is_valid_bot_token

log = get_logger(__name__)
router = Router(name="private:tenant_bot")


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_tenant_id(user_id: int) -> int | None:
    """Resolve tenant ID from the owner's Telegram user ID."""
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)
    return tenant.id if tenant else None


def _mask_token(token: str) -> str:
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def _status_icon(status: str) -> str:
    icons = {
        "running": "🟢",
        "starting": "🟡",
        "failed": "🔴",
        "stopped": "⚫",
        "paused": "⏸",
        "disconnected": "⚪",
        "not_registered": "🟠",
    }
    return icons.get(status, "❓")


def _status_label(status: str) -> str:
    labels = {
        "running": "Ishlayapti",
        "starting": "Ishga tushirilmoqda",
        "failed": "Xatolik",
        "stopped": "To'xtatilgan",
        "paused": "Pauza",
        "disconnected": "Ulanmagan",
        "not_registered": "Ro'yxatdan o'tmagan",
    }
    return labels.get(status, status)


def _connected_keyboard() -> InlineKeyboardMarkup:
    """Action buttons when bot is connected."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏥 Health Check", callback_data="tbot:health"),
            InlineKeyboardButton(text="🌐 Webhook", callback_data="tbot:webhook:toggle"),
        ],
        [
            InlineKeyboardButton(text="🔄 Qayta ulash", callback_data="tbot:reconnect"),
            InlineKeyboardButton(text="🔌 Uzish", callback_data="tbot:disconnect"),
        ],
    ])


def _disconnected_keyboard() -> InlineKeyboardMarkup:
    """Action buttons when bot is disconnected."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Bot ulash", callback_data="tbot:connect")],
    ])


def _confirm_connect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="tbot:connect:confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tbot:connect:cancel"),
        ],
    ])


def _confirm_disconnect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="tbot:dc:confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tbot:dc:cancel"),
        ],
    ])


def _confirm_reconnect_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="tbot:rc:confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tbot:rc:cancel"),
        ],
    ])


def _format_status(info: object) -> str:
    """Format BotStatusInfo for display."""
    icon = _status_icon(info.status)
    label = _status_label(info.status)
    username = f"@{info.bot_username}" if info.bot_username else "(sozlanmagan)"
    webhook = "✅ O'rnatilgan" if info.webhook_set else "❌ O'rnatilmagan"
    health = (
        info.last_health_check.strftime("%Y-%m-%d %H:%M UTC")
        if info.last_health_check
        else "—"
    )
    error = f"\nXatolik: {info.last_error}" if info.last_error else ""
    uptime = (
        f"\nIshga tushgan: {info.uptime_since.strftime('%Y-%m-%d %H:%M UTC')}"
        if info.uptime_since
        else ""
    )

    return (
        f"🤖 Bot holati\n\n"
        f"Bot: {username}\n"
        f"Holat: {icon} {label}\n"
        f"Webhook: {webhook}\n"
        f"So'nggi health check: {health}"
        f"{error}{uptime}"
    )


# ── /connect_bot ─────────────────────────────────────────────────────────────


@router.message(Command("connect_bot"), F.chat.type == "private")
async def cmd_connect_bot(message: Message, state: FSMContext, **data) -> None:
    """Start the bot connection flow."""
    user_id = message.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await message.answer(
            "Sizda biznes topilmadi.\n"
            "Avval /create_business buyrug'i bilan biznes yarating.",
        )
        return

    # Check if already connected
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        info = await svc.get_bot_status(tenant_id)

    if info and info.bot_username:
        await message.answer(
            f"Sizda allaqachon bot ulangan: @{info.bot_username}\n\n"
            "Boshqa botga o'tish uchun qayta ulash tugmasini bosing.",
            reply_markup=_connected_keyboard(),
        )
        return

    await state.clear()
    await state.update_data(tenant_id=tenant_id)
    await state.set_state(TenantBotConnectStates.waiting_for_token)
    await message.answer(
        "BotFather dan olgan tokenni yuboring.\n"
        "(Masalan: <code>123456789:ABCdef...</code>)\n\n"
        "⚠️ Xavfsizlik uchun xabaringiz avtomatik o'chiriladi.",
    )


@router.callback_query(F.data == "tbot:connect")
async def cb_connect(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Inline button entry point for connection."""
    await callback.answer()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if tenant_id is None:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    await state.clear()
    await state.update_data(tenant_id=tenant_id)
    await state.set_state(TenantBotConnectStates.waiting_for_token)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "BotFather dan olgan tokenni yuboring.\n"
        "(Masalan: <code>123456789:ABCdef...</code>)\n\n"
        "⚠️ Xavfsizlik uchun xabaringiz avtomatik o'chiriladi.",
    )


# ── Token input (connect) ───────────────────────────────────────────────────


@router.message(
    StateFilter(TenantBotConnectStates.waiting_for_token),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_connect_token(message: Message, state: FSMContext, **data) -> None:
    token = message.text.strip()

    # Delete the message for security
    try:
        await message.delete()
    except Exception:
        pass

    if not is_valid_bot_token(token):
        await message.answer(
            "Token formati noto'g'ri.\n"
            "To'g'ri format: <code>123456789:ABCdefGhi-JKLmnoPQR...</code>\n\n"
            "Qaytadan kiriting:",
        )
        return

    # Validate with Telegram API
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        try:
            bot_info = await svc.validate_token(token)
        except ValueError as exc:
            await message.answer(f"❌ {exc}\n\nQaytadan kiriting:")
            return
        except ConnectionError as exc:
            await message.answer(f"❌ {exc}\n\nQaytadan urinib ko'ring:")
            return

    await state.update_data(
        token=token,
        bot_username=bot_info.username,
        bot_first_name=bot_info.first_name,
        bot_id=bot_info.bot_id,
    )
    await state.set_state(TenantBotConnectStates.confirm_connect)

    username_display = f"@{bot_info.username}" if bot_info.username else "(username yo'q)"
    await message.answer(
        f"✅ Bot topildi!\n\n"
        f"Nomi: {bot_info.first_name}\n"
        f"Username: {username_display}\n"
        f"Token: {_mask_token(token)}\n\n"
        "Ulashni tasdiqlaysizmi?",
        reply_markup=_confirm_connect_keyboard(),
    )


# ── Confirm connect ──────────────────────────────────────────────────────────


@router.callback_query(
    StateFilter(TenantBotConnectStates.confirm_connect),
    F.data == "tbot:connect:confirm",
)
async def handle_connect_confirm(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    tenant_id = fsm_data["tenant_id"]
    token = fsm_data["token"]

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        try:
            info = await svc.connect_bot(tenant_id, token)
            await session.commit()
        except Exception as exc:
            log.exception("bot_connect_failed", tenant_id=tenant_id)
            await state.clear()
            await callback.message.answer(
                f"❌ Ulashda xatolik: {str(exc)[:200]}\n\n"
                "Qaytadan urinib ko'ring: /connect_bot",
            )
            return

    await state.clear()
    username = f"@{info.bot_username}" if info.bot_username else ""
    await callback.message.answer(
        f"✅ Bot muvaffaqiyatli ulandi! {username}\n\n"
        f"Holat: {_status_icon(info.status)} {_status_label(info.status)}\n\n"
        "Bot holatini ko'rish: /bot_status",
        reply_markup=_connected_keyboard(),
    )


@router.callback_query(
    StateFilter(TenantBotConnectStates.confirm_connect),
    F.data == "tbot:connect:cancel",
)
async def handle_connect_cancel(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await callback.message.answer("Bot ulash bekor qilindi.")


# ── /bot_status ──────────────────────────────────────────────────────────────


@router.message(Command("bot_status"), F.chat.type == "private")
async def cmd_bot_status(message: Message, **data) -> None:
    """Show bot connection status."""
    user_id = message.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await message.answer(
            "Sizda biznes topilmadi.\n"
            "Avval /create_business buyrug'i bilan biznes yarating.",
        )
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        info = await svc.get_bot_status(tenant_id)

    if info is None:
        await message.answer("Bot holati topilmadi.")
        return

    keyboard = _connected_keyboard() if info.bot_username else _disconnected_keyboard()
    await message.answer(_format_status(info), reply_markup=keyboard)


# ── /disconnect_bot ──────────────────────────────────────────────────────────


@router.message(Command("disconnect_bot"), F.chat.type == "private")
async def cmd_disconnect_bot(message: Message, **data) -> None:
    """Start disconnect confirmation."""
    user_id = message.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await message.answer("Sizda biznes topilmadi.")
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        info = await svc.get_bot_status(tenant_id)

    if info is None or not info.bot_username:
        await message.answer("Hozirda bot ulanmagan.")
        return

    await message.answer(
        f"@{info.bot_username} botni uzishni tasdiqlaysizmi?\n\n"
        "⚠️ Barcha webhook va ulanish bekor qilinadi.",
        reply_markup=_confirm_disconnect_keyboard(),
    )


@router.callback_query(F.data == "tbot:disconnect")
async def cb_disconnect(callback: CallbackQuery, **data) -> None:
    """Inline button for disconnect confirmation."""
    await callback.answer()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        info = await svc.get_bot_status(tenant_id)

    if info is None or not info.bot_username:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Hozirda bot ulanmagan.")
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"@{info.bot_username} botni uzishni tasdiqlaysizmi?\n\n"
        "⚠️ Barcha webhook va ulanish bekor qilinadi.",
        reply_markup=_confirm_disconnect_keyboard(),
    )


@router.callback_query(F.data == "tbot:dc:confirm")
async def handle_disconnect_confirm(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if tenant_id is None:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        ok = await svc.disconnect_bot(tenant_id)
        await session.commit()

    if ok:
        await callback.message.answer(
            "✅ Bot uzildi.\n\n"
            "Yangi bot ulash uchun: /connect_bot",
            reply_markup=_disconnected_keyboard(),
        )
    else:
        await callback.message.answer("❌ Uzishda xatolik yuz berdi.")


@router.callback_query(F.data == "tbot:dc:cancel")
async def handle_disconnect_cancel(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Bot uzish bekor qilindi.")


# ── Reconnect ────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "tbot:reconnect")
async def cb_reconnect(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Enter reconnect flow."""
    await callback.answer()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    await state.clear()
    await state.update_data(tenant_id=tenant_id)
    await state.set_state(TenantBotReconnectStates.waiting_for_new_token)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Yangi bot tokenini kiriting.\n"
        "(BotFather dan olgan token)\n\n"
        "⚠️ Xavfsizlik uchun xabaringiz avtomatik o'chiriladi.",
    )


@router.message(
    StateFilter(TenantBotReconnectStates.waiting_for_new_token),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_reconnect_token(message: Message, state: FSMContext, **data) -> None:
    token = message.text.strip()

    try:
        await message.delete()
    except Exception:
        pass

    if not is_valid_bot_token(token):
        await message.answer(
            "Token formati noto'g'ri. Qaytadan kiriting:",
        )
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        try:
            bot_info = await svc.validate_token(token)
        except ValueError as exc:
            await message.answer(f"❌ {exc}\n\nQaytadan kiriting:")
            return
        except ConnectionError as exc:
            await message.answer(f"❌ {exc}\n\nQaytadan urinib ko'ring:")
            return

    await state.update_data(
        new_token=token,
        bot_username=bot_info.username,
        bot_first_name=bot_info.first_name,
    )
    await state.set_state(TenantBotReconnectStates.confirm_reconnect)

    username_display = f"@{bot_info.username}" if bot_info.username else "(username yo'q)"
    await message.answer(
        f"✅ Yangi bot topildi!\n\n"
        f"Nomi: {bot_info.first_name}\n"
        f"Username: {username_display}\n"
        f"Token: {_mask_token(token)}\n\n"
        "Qayta ulashni tasdiqlaysizmi?\n"
        "⚠️ Eski bot uziladi.",
        reply_markup=_confirm_reconnect_keyboard(),
    )


@router.callback_query(
    StateFilter(TenantBotReconnectStates.confirm_reconnect),
    F.data == "tbot:rc:confirm",
)
async def handle_reconnect_confirm(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    tenant_id = fsm_data["tenant_id"]
    new_token = fsm_data["new_token"]

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        try:
            info = await svc.reconnect_bot(tenant_id, new_token)
            await session.commit()
        except Exception as exc:
            log.exception("bot_reconnect_failed", tenant_id=tenant_id)
            await state.clear()
            await callback.message.answer(
                f"❌ Qayta ulashda xatolik: {str(exc)[:200]}",
            )
            return

    await state.clear()
    username = f"@{info.bot_username}" if info.bot_username else ""
    await callback.message.answer(
        f"✅ Bot muvaffaqiyatli qayta ulandi! {username}\n\n"
        f"Holat: {_status_icon(info.status)} {_status_label(info.status)}\n\n"
        "Bot holatini ko'rish: /bot_status",
        reply_markup=_connected_keyboard(),
    )


@router.callback_query(
    StateFilter(TenantBotReconnectStates.confirm_reconnect),
    F.data == "tbot:rc:cancel",
)
async def handle_reconnect_cancel(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await callback.message.answer("Qayta ulash bekor qilindi.")


# ── Health Check ─────────────────────────────────────────────────────────────


@router.callback_query(F.data == "tbot:health")
async def cb_health_check(callback: CallbackQuery, **data) -> None:
    """Run a health check on the tenant's bot."""
    await callback.answer("Tekshirilmoqda...")
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        info = await svc.health_check(tenant_id)
        await session.commit()

    if info is None:
        await callback.message.answer("Bot holati topilmadi.")
        return

    if info.last_error:
        await callback.message.answer(
            f"❌ Health check muvaffaqiyatsiz.\n\n{_format_status(info)}",
            reply_markup=_connected_keyboard(),
        )
    else:
        await callback.message.answer(
            f"✅ Health check muvaffaqiyatli!\n\n{_format_status(info)}",
            reply_markup=_connected_keyboard(),
        )


# ── Webhook Toggle ───────────────────────────────────────────────────────────


@router.callback_query(F.data == "tbot:webhook:toggle")
async def cb_webhook_toggle(callback: CallbackQuery, **data) -> None:
    """Toggle webhook on/off."""
    await callback.answer()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)

    if tenant_id is None:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        info = await svc.get_bot_status(tenant_id)

        if info is None:
            await callback.message.answer("Bot holati topilmadi.")
            return

        try:
            if info.webhook_set:
                await svc.remove_webhook(tenant_id)
                await session.commit()
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.answer(
                    "✅ Webhook o'chirildi.",
                    reply_markup=_connected_keyboard(),
                )
            else:
                ok = await svc.set_webhook(tenant_id)
                await session.commit()
                await callback.message.edit_reply_markup(reply_markup=None)
                if ok:
                    await callback.message.answer(
                        "✅ Webhook o'rnatildi.",
                        reply_markup=_connected_keyboard(),
                    )
                else:
                    await callback.message.answer(
                        "❌ Webhook o'rnatib bo'lmadi.\n"
                        "Bot registrda ro'yxatdan o'tganligini tekshiring.",
                        reply_markup=_connected_keyboard(),
                    )
        except Exception as exc:
            log.exception("webhook_toggle_failed", tenant_id=tenant_id)
            await callback.message.answer(
                f"❌ Xatolik: {str(exc)[:200]}",
                reply_markup=_connected_keyboard(),
            )
