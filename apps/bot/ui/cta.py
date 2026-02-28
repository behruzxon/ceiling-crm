"""
apps.bot.ui.cta
~~~~~~~~~~~~~~~
Reusable CTA (call-to-action) keyboard builders and send helper.

Public API
----------
- cta_keyboard()              — 2-button discount + order keyboard
- cta_discount_keyboard()     — 3-button extended keyboard shown after tapping discount
- cta_intent_keyboard(text)   — dynamic buttons chosen by keyword intent in user text
- send_cta(bot, chat_id, reason) — fire-and-forget CTA message send

Callback data namespace: ``cta:*``
Handled by apps.bot.handlers.callbacks.cta_callbacks.
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

# ── Keyword sets for intent detection ─────────────────────────────────────────

_PRICING_KW: frozenset[str] = frozenset({"narx", "necha", "kv", "hisob"})
_ORDER_KW:   frozenset[str] = frozenset({"zakaz", "buyurtma", "o'lchov", "kelib"})


# ── Keyboard builders ──────────────────────────────────────────────────────────


def cta_keyboard() -> InlineKeyboardMarkup:
    """Standard 2-button CTA: discount + order.

    The discount button label includes the configured percent suffix when
    ``settings.cta.discount_percent`` is set.
    """
    settings = get_settings()
    pct_suffix = (
        f" (-{settings.cta.discount_percent}%)"
        if settings.cta.discount_percent
        else ""
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔥 Chegirma aktiv!{pct_suffix}",
                callback_data="cta:discount",
            )],
            [InlineKeyboardButton(
                text="🛒 Zakaz berish",
                callback_data="cta:order",
            )],
        ]
    )


def cta_discount_keyboard() -> InlineKeyboardMarkup:
    """Extended 3-button keyboard shown after the user taps the discount button."""
    settings = get_settings()
    pct_suffix = (
        f" (-{settings.cta.discount_percent}%)"
        if settings.cta.discount_percent
        else ""
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔥 Chegirma aktiv!{pct_suffix}",
                callback_data="cta:discount",
            )],
            [InlineKeyboardButton(
                text="💰 Narx kalkulyator",
                callback_data="cta:pricing",
            )],
            [InlineKeyboardButton(
                text="🛒 Zakaz berish",
                callback_data="cta:order",
            )],
        ]
    )


def cta_intent_keyboard(user_text: str) -> InlineKeyboardMarkup:
    """Choose CTA buttons based on keyword intent detection in user_text.

    Intent rules (checked in order):
    - pricing: any of {"narx", "necha", "kv", "hisob"} found in lowercased text
    - order:   any of {"zakaz", "buyurtma", "o'lchov", "kelib"}
    - generic: fallback
    """
    lower = user_text.lower()

    if any(kw in lower for kw in _PRICING_KW):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="💰 Narx kalkulyator",
                    callback_data="cta:pricing",
                )],
                [InlineKeyboardButton(
                    text="🛒 Zakaz berish",
                    callback_data="cta:order",
                )],
            ]
        )

    if any(kw in lower for kw in _ORDER_KW):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🛒 Zakaz berish",
                    callback_data="cta:order",
                )],
                [InlineKeyboardButton(
                    text="☎️ Operator",
                    callback_data="cta:operator",
                )],
            ]
        )

    # Generic fallback
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🛒 Zakaz berish",
                callback_data="cta:order",
            )],
            [InlineKeyboardButton(
                text="📂 Katalog",
                callback_data="cta:catalog",
            )],
        ]
    )


# ── Send helper ────────────────────────────────────────────────────────────────


async def send_cta(bot: Bot, chat_id: int, reason: str = "generic") -> None:
    """Send a CTA message with the standard 2-button keyboard.

    Respects ``settings.cta.enabled`` — silently returns when disabled.
    Intended for fire-and-forget use; caller should wrap in try/except.

    Args:
        bot:     Aiogram Bot instance.
        chat_id: Telegram chat/user ID to send to.
        reason:  Label for structured log (e.g. "inactive_5m", "start").
    """
    settings = get_settings()
    if not settings.cta.enabled:
        return
    await bot.send_message(
        chat_id=chat_id,
        text=settings.cta.discount_text,
        reply_markup=cta_keyboard(),
    )
    log.info("cta_sent", chat_id=chat_id, reason=reason)
