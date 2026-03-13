"""
apps.bot.handlers.private.packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"📦 Tayyor paketlar" — ready-made package browser and order flow.

User flow
---------
  Main menu "📦 Tayyor paketlar"
    → Package list (inline keyboard)
      → Package detail (description + actions)
        → "📐 Hisoblash"   — price estimate table
        → "📝 Zakaz berish" — upsert lead + admin notification + follow-up task
        → "📞 Operator"    — operator contact info
        → "⬅️ Ortga"       — back to package list
      → "⬅️ Ortga"         — back to main menu message

CRM side effects for "Zakaz berish"
-------------------------------------
  - Lead upserted (upsert_package_lead)
  - pipeline_stages row inserted (PACKAGE_SELECTED)
  - Admin groups + admin DM notified with inline action buttons
  - Celery follow-up task scheduled for 15 minutes
"""
from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_service
from infrastructure.queue.tasks.package_tasks import check_package_followup
from apps.bot.keyboards.main_menu import BTN_PACKAGES
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:packages")

# ── Package catalogue (hardcoded) ──────────────────────────────────────────────

PACKAGE_INFO: dict[str, dict] = {
    "standard": {
        "name": "🥉 Standard",
        "description": (
            "🥉 <b>STANDARD — Eng arzon va tez variant</b>\n\n"
            "• Oddiy va ishonchli natijnoy patalok\n"
            "• ⚡ Eng tez o'rnatish\n"
            "• 💸 Har qanday boshqa potolok turidan arzon\n"
            "• 🎨 10+ rang tanlov\n"
            "• 🛡 10 yil kafolat\n\n"
            "💰 Narx: <b>80 000 UZS/m²</b>\n\n"
            "🎯 <i>Ijara uylari va byudjet variant uchun ideal</i>"
        ),
        "price_per_m2": 80_000,
        "score_delta": 5,
        "status": "warm",
    },
    "premium": {
        "name": "🥈 Premium ⭐",
        "description": (
            "🥈 <b>PREMIUM ⭐ Eng ko'p tanlanadi</b>\n\n"
            "• 🌸 Gulli dizayn variantlar\n"
            "• 🧩 Hi-tech zamonaviy uslub\n"
            "• 🪨 Mramor (marmar) effektli naqshlar\n"
            "• 🎨 10 000+ dizayn va faktura\n"
            "• 💡 LED bilan uyg'un dizayn\n"
            "• 🛡 10 yil kafolat\n\n"
            "💰 Narx: <b>120 000 UZS/m²</b>"
        ),
        "price_per_m2": 120_000,
        "score_delta": 10,
        "status": "hot",
    },
    "vip": {
        "name": "🥇 VIP 👑",
        "description": (
            "🥇 <b>VIP 👑 Eksklyuziv dizayn</b>\n\n"
            "• 🧩 Murakkab hi-tech dizaynlar\n"
            "• 💡 Spot chiroqlar integratsiyasi\n"
            "• ➖ Trek sistema\n"
            "• ✨ Svetavoy liniya\n"
            "• 🌈 RGB + ko'p darajali yoritish\n"
            "• 🏗 Ko'p bosqichli konstruktsiya\n"
            "• 🎨 Individual loyiha asosida dizayn\n"
            "• 📐 Bepul o'lchov + dizayn loyiha\n"
            "• 🛡 15 yil kafolat\n\n"
            "💰 Narx: <b>140 000 – 1 000 000 UZS/m²</b>"
        ),
        "price_per_m2": 140_000,
        "score_delta": 15,
        "status": "hot",
    },
}

_PACKAGES_LIST_TEXT = (
    "📦 <b>Tayyor paketlar</b>\n\n"
    "Eng qulay paketni tanlang va operator tez orada bog'lanadi:\n\n"
    "🥉 <b>Standard</b> — 80 000 UZS/m²\n"
    "🥈 <b>Premium</b> ⭐ — 120 000 UZS/m²  <i>(eng ko'p tanlanadi)</i>\n"
    "🥇 <b>VIP</b> 👑 — 140 000 – 1 000 000 UZS/m²\n\n"
    "👇 Paketni tanlang:"
)


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _packages_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🥉 Standard", callback_data="pkg:detail:standard"),
            InlineKeyboardButton(text="🥈 Premium ⭐", callback_data="pkg:detail:premium"),
            InlineKeyboardButton(text="🥇 VIP", callback_data="pkg:detail:vip"),
        ],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="pkg:back_main")],
    ])


def _package_detail_keyboard(pkg_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📐 Hisoblash", callback_data=f"pkg:calc:{pkg_key}")],
        [InlineKeyboardButton(text="📝 Zakaz berish", callback_data=f"pkg:order:{pkg_key}")],
        [InlineKeyboardButton(text="📞 Operator", callback_data="pkg:operator")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="pkg:back_list")],
    ])


async def show_packages_list(message: Message) -> None:
    """Show the package list inline keyboard.

    Public helper so the group menu callback in group/start.py can reuse
    this without duplicating the text + keyboard.
    """
    await message.answer(_PACKAGES_LIST_TEXT, reply_markup=_packages_list_keyboard())


def _price_estimate_keyboard(pkg_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Zakaz berish", callback_data=f"pkg:order:{pkg_key}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"pkg:detail:{pkg_key}")],
    ])


# ── Admin notification keyboard ────────────────────────────────────────────────

def _admin_action_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    lid = lead_id
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ HOT",   callback_data=f"pkg:admin:hot:{lid}"),
            InlineKeyboardButton(text="🟡 WARM",  callback_data=f"pkg:admin:warm:{lid}"),
            InlineKeyboardButton(text="❄️ COLD",  callback_data=f"pkg:admin:cold:{lid}"),
        ],
        [
            InlineKeyboardButton(text="📞 Telefon",    callback_data=f"pkg:admin:phone:{lid}"),
            InlineKeyboardButton(text="📅 O'lchov",    callback_data=f"pkg:admin:schedule:{lid}"),
        ],
        [
            InlineKeyboardButton(text="📝 Izoh",  callback_data=f"pkg:admin:note:{lid}"),
            InlineKeyboardButton(text="🚫 Block", callback_data=f"pkg:admin:block:{lid}"),
        ],
    ])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _admin_notification_text(
    lead_id: int,
    first_name: str,
    username: str | None,
    user_id: int,
    phone: str,
    pkg_name: str,
    lead_status: str,
    score: int,
) -> str:
    uname = f"@{username}" if username else "—"
    status_emoji = {"hot": "🔥", "warm": "🟡", "cold": "❄️"}.get(lead_status, "⬜")
    ts = datetime.now().strftime("%d.%m.%Y %H:%M")
    return (
        f"📦 <b>Yangi paket so'rovi!</b>\n\n"
        f"👤 Ism: <b>{first_name}</b>\n"
        f"🆔 Telegram: {uname} (<code>{user_id}</code>)\n"
        f"📱 Telefon: <code>{phone}</code>\n"
        f"📦 Paket: <b>{pkg_name}</b>\n"
        f"{status_emoji} Holat: <b>{lead_status.upper()}</b>\n"
        f"⭐ Score: <b>{score}</b>\n"
        f"📅 Vaqt: {ts}\n\n"
        f"Lead #{lead_id} | /lead_{lead_id}"
    )


async def _send_admin_notifications(
    lead_id: int,
    first_name: str,
    username: str | None,
    user_id: int,
    phone: str,
    pkg_name: str,
    lead_status: str,
    score: int,
) -> None:
    """Send lead card to admin DM + all admin groups.  Never raises."""
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties

    settings = get_settings()
    text = _admin_notification_text(
        lead_id, first_name, username, user_id, phone, pkg_name, lead_status, score
    )
    kb = _admin_action_keyboard(lead_id)

    bot = Bot(
        token=settings.bot.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    try:
        # Admin group only (no DM)
        admin_group_id = settings.bot.admin_group_id
        if admin_group_id:
            try:
                await bot.send_message(admin_group_id, text, reply_markup=kb)
            except Exception as exc:
                log.warning("pkg_admin_group_failed", chat_id=admin_group_id, error=str(exc))
        else:
            log.warning("pkg_admin_group_id_not_configured")

    finally:
        await bot.session.close()


# ── Handlers ───────────────────────────────────────────────────────────────────


@router.message(F.text == BTN_PACKAGES)
async def cmd_packages(message: Message, **data: object) -> None:
    """Show the package selection menu."""
    await message.answer(
        _PACKAGES_LIST_TEXT,
        reply_markup=_packages_list_keyboard(),
    )


@router.callback_query(F.data == "pkg:back_list")
async def cb_back_to_list(callback: CallbackQuery, **data: object) -> None:
    """Return to the package list from a detail view."""
    await callback.message.edit_text(  # type: ignore[union-attr]
        _PACKAGES_LIST_TEXT,
        reply_markup=_packages_list_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "pkg:back_main")
async def cb_back_main(callback: CallbackQuery, **data: object) -> None:
    """Close the package browser (delete inline message)."""
    await callback.message.delete()  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("pkg:detail:"))
async def cb_package_detail(callback: CallbackQuery, **data: object) -> None:
    """Show detailed description + action buttons for one package."""
    pkg_key = callback.data.split(":")[-1]  # type: ignore[union-attr]
    info = PACKAGE_INFO.get(pkg_key)
    if info is None:
        await callback.answer("Noma'lum paket", show_alert=True)
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        info["description"],
        reply_markup=_package_detail_keyboard(pkg_key),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pkg:calc:"))
async def cb_package_calc(callback: CallbackQuery, **data: object) -> None:
    """Show a quick price estimate table for the selected package."""
    pkg_key = callback.data.split(":")[-1]  # type: ignore[union-attr]
    info = PACKAGE_INFO.get(pkg_key)
    if info is None:
        await callback.answer("Noma'lum paket", show_alert=True)
        return

    price = info["price_per_m2"]
    text = (
        f"📐 <b>{info['name']} — taxminiy narxlar</b>\n\n"
        f"• 10 m² → {price * 10:,} UZS\n"
        f"• 20 m² → {price * 20:,} UZS\n"
        f"• 30 m² → {price * 30:,} UZS\n"
        f"• 50 m² → {price * 50:,} UZS\n\n"
        f"Aniq narx uchun o'lchovni kiritib, kalkulyatorni ishlating: "
        f"🧮 Narx kalkulyator"
    )
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_price_estimate_keyboard(pkg_key),
    )
    await callback.answer()


@router.callback_query(F.data == "pkg:operator")
async def cb_operator(callback: CallbackQuery, **data: object) -> None:
    """Show operator contact details."""
    await callback.answer(
        "📞 Operator: +998 90 000 00 00\n"
        "Ish vaqti: 09:00 – 18:00",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("pkg:order:"))
async def cb_package_order(callback: CallbackQuery, **data: object) -> None:
    """Create / update lead, notify admins, schedule follow-up."""
    pkg_key = callback.data.split(":")[-1]  # type: ignore[union-attr]
    info = PACKAGE_INFO.get(pkg_key)
    if info is None:
        await callback.answer("Noma'lum paket", show_alert=True)
        return

    user = callback.from_user  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            lead_service = get_lead_service(session)
            lead = await lead_service.select_package(
                user_id=user.id,
                package_type=pkg_key,
                first_name=user.first_name,
                score_delta=info["score_delta"],
                lead_status=info["status"],
            )
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("pkg_order_db_error", user_id=user.id, pkg_key=pkg_key)
            await callback.answer("Xatolik yuz berdi, qayta urinib ko'ring.", show_alert=True)
            return

    # Confirm to user immediately (non-blocking — admin notifications happen after)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ <b>So'rovingiz qabul qilindi!</b>\n\n"
        f"📦 Paket: <b>{info['name']}</b>\n\n"
        f"👤 Operator tez orada bog'lanadi.\n"
        f"📞 Tezroq aloqa uchun /operator buyrug'ini yuboring.",
        reply_markup=None,
    )
    await callback.answer("✅ Qabul qilindi!")

    # Admin notifications (best-effort, non-fatal)
    try:
        await _send_admin_notifications(
            lead_id=lead.id,
            first_name=user.first_name,
            username=user.username,
            user_id=user.id,
            phone=lead.phone,
            pkg_name=info["name"],
            lead_status=info["status"],
            score=lead.score,
        )
    except Exception:
        log.exception("pkg_admin_notify_error", lead_id=lead.id)

    # HOT lead alert if applicable (fire-and-forget, deduped internally)
    try:
        from core.services.lead_notification_service import is_hot_lead
        from infrastructure.di import get_lead_notification_service
        if is_hot_lead(lead):
            await get_lead_notification_service().notify_hot_lead(lead.id)
    except Exception:
        log.exception("pkg_hot_lead_notify_error", lead_id=lead.id)

    # Schedule follow-up check in 15 minutes (idempotent Celery task)
    try:
        check_package_followup.apply_async(
            args=[lead.id],
            countdown=15 * 60,
        )
        log.info("pkg_followup_scheduled", lead_id=lead.id)
    except Exception:
        log.warning("pkg_followup_schedule_failed", lead_id=lead.id)
