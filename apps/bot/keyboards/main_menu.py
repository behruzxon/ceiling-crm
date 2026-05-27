"""Main menu reply keyboard builder and button-text constants."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

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


def main_menu_keyboard(
    locale: str = "uz",
    is_admin: bool = False,
    selective: bool = False,
) -> ReplyKeyboardMarkup:
    """Build main menu keyboard.

    Args:
        locale: Language code (unused for now, reserved for i18n).
        is_admin: When True, appends the admin-only "📣 Rassilka" button.
        selective: When True, keyboard is shown only to the replied-to user
                   (use with message.reply()).  Sets is_persistent=False.
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
        is_persistent=not selective,
        one_time_keyboard=False,
        selective=selective,
    )


def group_menu_kb_full() -> InlineKeyboardMarkup:
    """Full 9-button URL inline keyboard for group chats.

    Each button deep-links into the bot's private DM with a /start payload,
    routing users to the appropriate feature flow.
    """
    from shared.config import get_settings
    bot_username = get_settings().bot.username

    def _url(payload: str) -> str:
        return f"https://t.me/{bot_username}?start={payload}"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_ORDER,     url=_url("zakaz")),
                InlineKeyboardButton(text=BTN_PRICE,     url=_url("price")),
            ],
            [
                InlineKeyboardButton(text=BTN_CATALOG,   url=_url("katalog")),
                InlineKeyboardButton(text=BTN_PACKAGES,  url=_url("paketlar")),
            ],
            [
                InlineKeyboardButton(text=BTN_MY_ORDERS, url=_url("orders")),
                InlineKeyboardButton(text=BTN_OPERATOR,  url=_url("operator")),
            ],
            [
                InlineKeyboardButton(text=BTN_PROMOS,    url=_url("discounts")),
                InlineKeyboardButton(text=BTN_AI,        url=_url("ai")),
            ],
            [
                InlineKeyboardButton(text=BTN_ABOUT,     url=_url("about")),
            ],
        ]
    )


def group_menu_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline menu for group/supergroup chats.

    ReplyKeyboardMarkup is unreliable in groups: it is only shown to the user
    who triggered the command, other members don't see it, and with bot privacy
    mode enabled the bot never receives the resulting plain-text taps at all.

    InlineKeyboard buttons produce callback_query updates that are always
    delivered to the bot regardless of privacy mode — making this the only
    reliable menu mechanism for groups.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=BTN_ORDER,     callback_data="grpmenu:order"),
                InlineKeyboardButton(text=BTN_PRICE,     callback_data="grpmenu:price"),
            ],
            [
                InlineKeyboardButton(text=BTN_CATALOG,   callback_data="grpmenu:catalog"),
                InlineKeyboardButton(text=BTN_PACKAGES,  callback_data="grpmenu:packages"),
            ],
            [
                InlineKeyboardButton(text=BTN_MY_ORDERS, callback_data="grpmenu:my_orders"),
                InlineKeyboardButton(text=BTN_OPERATOR,  callback_data="grpmenu:operator"),
            ],
            [
                InlineKeyboardButton(text=BTN_PROMOS,    callback_data="grpmenu:promos"),
                InlineKeyboardButton(text=BTN_AI,        callback_data="grpmenu:ai"),
            ],
            [
                InlineKeyboardButton(text=BTN_ABOUT,     callback_data="grpmenu:about"),
            ],
        ]
    )
