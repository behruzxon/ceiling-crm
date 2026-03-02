"""
Catalog browsing handler.

FSM flow
--------
  BTN_CATALOG / /catalog
    └─► CatalogStates.waiting_for_design   ← ReplyKeyboard with 10 design buttons
          ├─ design title tapped → send link + caption, stay in state
          └─ "⬅️ Orqaga"        → clear state → main menu

AI is NOT involved: handle_ai_message uses StateFilter(default_state) so it
never fires while waiting_for_design is active.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.keyboards.catalog import BTN_CATALOG_BACK, catalog_design_keyboard
from apps.bot.keyboards.main_menu import BTN_CATALOG, MAIN_MENU_BUTTONS, main_menu_keyboard
from apps.bot.states.catalog import CatalogStates
from shared.constants.catalog import CATALOG
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:catalog")

_CHAT_TYPES = {"private", "group", "supergroup"}

# Reverse lookup: display title → CatalogSection (built once at import).
_CATALOG_BY_TITLE = {s.title: s for s in CATALOG}


# ── Entry ─────────────────────────────────────────────────────────────────────

@router.message(F.chat.type.in_(_CHAT_TYPES), F.text == BTN_CATALOG)
@router.message(F.chat.type.in_(_CHAT_TYPES), Command("catalog"))
async def cmd_catalog(message: Message, state: FSMContext, **data: object) -> None:
    """Show design selection keyboard and enter catalog FSM state."""
    await state.set_state(CatalogStates.waiting_for_design)
    await message.answer(
        "📂 <b>Katalog</b>\n\nDizaynni tanlang:",
        reply_markup=catalog_design_keyboard(),
    )


# ── Back button ───────────────────────────────────────────────────────────────

@router.message(
    StateFilter(CatalogStates.waiting_for_design),
    F.text == BTN_CATALOG_BACK,
)
async def handle_catalog_back(message: Message, state: FSMContext, **data: object) -> None:
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=main_menu_keyboard())


# ── Design selection ──────────────────────────────────────────────────────────

@router.message(
    StateFilter(CatalogStates.waiting_for_design),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),   # let main-menu taps fall through
    ~F.text.startswith("/"),
)
async def handle_design_choice(
    message: Message, state: FSMContext, **data: object
) -> None:
    text = (message.text or "").strip()

    if text == BTN_CATALOG_BACK:
        return

    section = _CATALOG_BY_TITLE.get(text)
    if section is None:
        await message.answer(
            "Iltimos, quyidagi dizaynlardan birini tanlang:",
            reply_markup=catalog_design_keyboard(),
        )
        return

    # Send link + caption; keep state so user can keep browsing
    await message.answer(
        f"<b>{section.title}</b>\n\n"
        f"📎 {section.group_url}",
        reply_markup=catalog_design_keyboard(),
    )
    log.info("catalog_design_viewed", key=section.key, user_id=getattr(message.from_user, "id", 0))
