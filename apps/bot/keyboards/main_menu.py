"""Main menu reply keyboard builder and button-text constants."""
from __future__ import annotations
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# ── Button text constants ─────────────────────────────────────────────────────
# Single source of truth for all main-menu button labels.
# Import these in handlers and use F.text == BTN_* for exact matching.
BTN_ORDER     = "🛒 Zakaz berish"
BTN_PRICE     = "💰 Narx kalkulyator"
BTN_CATALOG   = "📂 Katalog"
BTN_PACKAGES  = "🎁 Tayyor paketlar"
BTN_MY_ORDERS = "📦 Buyurtmalarim"
BTN_OPERATOR  = "☎️ Operator"
BTN_PROMOS    = "🎉 Chegirmalar"
BTN_AI        = "🤖 AI yordam"
BTN_ABOUT     = "⭐ Biz haqimizda"

# Frozenset of all 9 main-menu button texts — useful for escape-state checks.
MAIN_MENU_BUTTONS: frozenset[str] = frozenset({
    BTN_ORDER, BTN_PRICE, BTN_CATALOG, BTN_PACKAGES,
    BTN_MY_ORDERS, BTN_OPERATOR, BTN_PROMOS, BTN_AI, BTN_ABOUT,
})


def main_menu_keyboard(locale: str = "uz", is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Build main menu keyboard.

    Args:
        locale: Language code (unused for now, reserved for i18n).
        is_admin: When True, appends the admin-only "📣 Rassilka" button.
    """
    rows = [
        [KeyboardButton(text=BTN_ORDER),     KeyboardButton(text=BTN_PRICE)],
        [KeyboardButton(text=BTN_CATALOG),   KeyboardButton(text=BTN_PACKAGES)],
        [KeyboardButton(text=BTN_MY_ORDERS), KeyboardButton(text=BTN_OPERATOR)],
        [KeyboardButton(text=BTN_PROMOS),    KeyboardButton(text=BTN_AI)],
        [KeyboardButton(text=BTN_ABOUT)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="📣 Rassilka")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )
