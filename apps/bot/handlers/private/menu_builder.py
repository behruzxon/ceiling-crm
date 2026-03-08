"""
apps.bot.handlers.private.menu_builder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tenant menu builder — allows business owners to customize their bot menu.

Supports view/add/edit/delete/reorder/restore buttons.
Two button types: action (mapped to existing handlers) and static (text response).

All inline callbacks use the ``mb:`` prefix.
"""
from __future__ import annotations

import copy
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.keyboards.main_menu import main_menu_keyboard
from apps.bot.states.menu_builder import MenuBuilderStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_tenant_service
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:menu_builder")

# ── Known action buttons ─────────────────────────────────────────────────────
# Maps action key → display description (shown when selecting action type)

KNOWN_ACTIONS: dict[str, str] = {
    "order": "Zakaz berish",
    "pricing": "Narx kalkulyator",
    "catalog": "Katalog",
    "packages": "Tayyor paketlar",
    "my_orders": "Buyurtmalarim",
    "operator": "Operator",
    "promos": "Chegirmalar",
    "ai": "AI yordam",
    "about": "Biz haqimizda",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_menu_config(menu_config: dict | None) -> list[list[dict]]:
    """Convert menu_config buttons to normalized list[list[dict]] format.

    Handles both old format (string arrays) and new format (dict arrays).
    """
    if not menu_config:
        return []
    buttons = menu_config.get("buttons", [])
    rows: list[list[dict]] = []
    for row in buttons:
        if not isinstance(row, list):
            continue
        normalized_row: list[dict] = []
        for item in row:
            if isinstance(item, str):
                # Old format: plain string → action button
                normalized_row.append({"text": item, "type": "action", "action": ""})
            elif isinstance(item, dict) and "text" in item:
                normalized_row.append(item)
        if normalized_row:
            rows.append(normalized_row)
    return rows


def _build_menu_config(rows: list[list[dict]], admin_buttons: list | None = None) -> dict:
    """Build menu_config dict from normalized rows."""
    return {
        "buttons": rows,
        "admin_buttons": admin_buttons or [["📣 Rassilka"]],
    }


def _render_menu_preview(rows: list[list[dict]]) -> str:
    """Render numbered text preview of menu buttons."""
    if not rows:
        return "(Menyu bo'sh)"
    lines: list[str] = []
    n = 1
    for row_idx, row in enumerate(rows):
        parts: list[str] = []
        for btn in row:
            btn_type = btn.get("type", "action")
            label = btn.get("text", "?")
            if btn_type == "static":
                parts.append(f"  {n}. {label} [matn]")
            else:
                action = btn.get("action", "")
                action_label = f" → {action}" if action else ""
                parts.append(f"  {n}. {label}{action_label}")
            n += 1
        lines.append(f"Qator {row_idx + 1}:\n" + "\n".join(parts))
    return "\n".join(lines)


def _flat_buttons(rows: list[list[dict]]) -> list[tuple[int, int, dict]]:
    """Flatten rows into (row_idx, col_idx, button_dict) list."""
    result = []
    for r_idx, row in enumerate(rows):
        for c_idx, btn in enumerate(row):
            result.append((r_idx, c_idx, btn))
    return result


def _viewing_keyboard() -> InlineKeyboardMarkup:
    """Action buttons shown in viewing state."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Qo'shish", callback_data="mb:add"),
            InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="mb:edit"),
        ],
        [
            InlineKeyboardButton(text="🗑 O'chirish", callback_data="mb:delete"),
            InlineKeyboardButton(text="🔀 Tartib", callback_data="mb:reorder"),
        ],
        [
            InlineKeyboardButton(text="♻️ Shablon qaytarish", callback_data="mb:restore"),
            InlineKeyboardButton(text="✅ Tayyor", callback_data="mb:done"),
        ],
    ])


def _type_keyboard() -> InlineKeyboardMarkup:
    """Button type selection: action or static."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Amal (action)", callback_data="mb:btype:action"),
            InlineKeyboardButton(text="Matn (static)", callback_data="mb:btype:static"),
        ],
    ])


def _action_keyboard() -> InlineKeyboardMarkup:
    """Known actions selection keyboard."""
    rows: list[list[InlineKeyboardButton]] = []
    items = list(KNOWN_ACTIONS.items())
    for i in range(0, len(items), 2):
        row = [
            InlineKeyboardButton(
                text=desc, callback_data=f"mb:action:{key}",
            )
            for key, desc in items[i:i + 2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _row_keyboard(num_rows: int) -> InlineKeyboardMarkup:
    """Select which row to place a new button in."""
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(num_rows):
        rows.append([InlineKeyboardButton(
            text=f"Qator {i + 1}", callback_data=f"mb:row:{i}",
        )])
    rows.append([InlineKeyboardButton(
        text="Yangi qator", callback_data=f"mb:row:{num_rows}",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _number_keyboard(count: int, prefix: str) -> InlineKeyboardMarkup:
    """Number selection keyboard (1..count)."""
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, count, 3):
        row = [
            InlineKeyboardButton(
                text=str(j + 1), callback_data=f"mb:{prefix}:{j}",
            )
            for j in range(i, min(i + 3, count))
        ]
        rows.append(row)
    rows.append([InlineKeyboardButton(text="Bekor qilish", callback_data="mb:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Ha, o'chirish", callback_data="mb:delconfirm:yes"),
            InlineKeyboardButton(text="Yo'q", callback_data="mb:delconfirm:no"),
        ],
    ])


def _direction_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬆️ Yuqoriga", callback_data="mb:dir:up"),
            InlineKeyboardButton(text="⬇️ Pastga", callback_data="mb:dir:down"),
        ],
        [InlineKeyboardButton(text="Bekor qilish", callback_data="mb:cancel")],
    ])


def _edit_field_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Matnni o'zgartirish", callback_data="mb:efield:text")],
        [InlineKeyboardButton(text="Bekor qilish", callback_data="mb:cancel")],
    ])


async def _load_tenant_menu(user_id: int) -> tuple[Any, list[list[dict]], list | None]:
    """Load tenant + normalized menu rows. Returns (tenant, rows, admin_buttons)."""
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)
    if not tenant:
        return None, [], None
    rows = _normalize_menu_config(tenant.menu_config)
    admin_buttons = (tenant.menu_config or {}).get("admin_buttons")
    return tenant, rows, admin_buttons


async def _save_menu(user_id: int, rows: list[list[dict]], admin_buttons: list | None) -> bool:
    """Save menu_config to tenant. Returns True on success."""
    menu_config = _build_menu_config(rows, admin_buttons)
    try:
        factory = get_session_factory()
        async with factory() as session:
            svc = get_tenant_service(session)
            await svc.update_tenant_field(user_id, menu_config=menu_config)
            await session.commit()
        return True
    except Exception:
        log.exception("menu_builder_save_failed", user_id=user_id)
        return False


async def _show_menu_view(target: Message | CallbackQuery, state: FSMContext) -> None:
    """Show menu preview + action buttons. Works with both Message and CallbackQuery."""
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    preview = _render_menu_preview(rows)

    text = f"Menyu tahrirlash:\n\n{preview}\n\nAmalni tanlang:"
    if isinstance(target, CallbackQuery):
        await target.message.answer(text, reply_markup=_viewing_keyboard())
    else:
        await target.answer(text, reply_markup=_viewing_keyboard())


# ── Entry points ─────────────────────────────────────────────────────────────

@router.message(Command("edit_menu"), F.chat.type == "private")
async def cmd_edit_menu(message: Message, state: FSMContext, **data) -> None:
    """Start menu builder via /edit_menu command."""
    user_id = message.from_user.id
    tenant, rows, admin_buttons = await _load_tenant_menu(user_id)
    if not tenant:
        await message.answer("Biznesingiz topilmadi. Avval /create_business buyrug'ini yuboring.")
        return

    await state.clear()
    await state.update_data(mb_rows=rows, mb_admin_buttons=admin_buttons)
    await state.set_state(MenuBuilderStates.viewing)
    await _show_menu_view(message, state)


@router.callback_query(F.data == "onb:edit:menu")
async def handle_edit_menu_callback(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Start menu builder from /my_business inline button."""
    await callback.answer()
    user_id = callback.from_user.id
    tenant, rows, admin_buttons = await _load_tenant_menu(user_id)
    if not tenant:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    await state.clear()
    await state.update_data(mb_rows=rows, mb_admin_buttons=admin_buttons)
    await state.set_state(MenuBuilderStates.viewing)
    await _show_menu_view(callback, state)


# ── Cancel (return to viewing) ───────────────────────────────────────────────

@router.callback_query(
    F.data == "mb:cancel",
    StateFilter(
        MenuBuilderStates.add_button_text, MenuBuilderStates.add_button_type,
        MenuBuilderStates.add_button_action, MenuBuilderStates.add_button_response,
        MenuBuilderStates.add_button_row, MenuBuilderStates.edit_select,
        MenuBuilderStates.edit_field, MenuBuilderStates.edit_value,
        MenuBuilderStates.delete_select, MenuBuilderStates.delete_confirm,
        MenuBuilderStates.reorder_select, MenuBuilderStates.reorder_direction,
    ),
)
async def handle_cancel(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.set_state(MenuBuilderStates.viewing)
    await _show_menu_view(callback, state)


# ── ADD button flow ──────────────────────────────────────────────────────────

@router.callback_query(StateFilter(MenuBuilderStates.viewing), F.data == "mb:add")
async def handle_add_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.set_state(MenuBuilderStates.add_button_text)
    await callback.message.answer("Yangi tugma matnini kiriting (masalan: 📋 Xizmatlar):")


@router.message(
    StateFilter(MenuBuilderStates.add_button_text),
    F.text, ~F.text.startswith("/"),
)
async def handle_add_text(message: Message, state: FSMContext, **data) -> None:
    text = message.text.strip()
    if len(text) < 1 or len(text) > 64:
        await message.answer("Matn 1 dan 64 belgigacha. Qaytadan kiriting:")
        return
    await state.update_data(mb_new_text=text)
    await state.set_state(MenuBuilderStates.add_button_type)
    await message.answer(
        "Tugma turini tanlang:",
        reply_markup=_type_keyboard(),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.add_button_type),
    F.data == "mb:btype:action",
)
async def handle_add_type_action(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.update_data(mb_new_type="action")
    await state.set_state(MenuBuilderStates.add_button_action)
    await callback.message.answer(
        "Qaysi amalga bog'lash?",
        reply_markup=_action_keyboard(),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.add_button_type),
    F.data == "mb:btype:static",
)
async def handle_add_type_static(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.update_data(mb_new_type="static")
    await state.set_state(MenuBuilderStates.add_button_response)
    await callback.message.answer(
        "Tugma bosilganda chiqadigan javob matnini kiriting:"
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.add_button_action),
    F.data.startswith("mb:action:"),
)
async def handle_add_action_select(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    action = callback.data.replace("mb:action:", "")
    if action not in KNOWN_ACTIONS:
        await callback.message.answer("Noto'g'ri tanlov. Qaytadan tanlang:", reply_markup=_action_keyboard())
        return
    await state.update_data(mb_new_action=action)
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    await state.set_state(MenuBuilderStates.add_button_row)
    await callback.message.answer(
        "Qaysi qatorga joylashtirish?",
        reply_markup=_row_keyboard(len(rows)),
    )


@router.message(
    StateFilter(MenuBuilderStates.add_button_response),
    F.text, ~F.text.startswith("/"),
)
async def handle_add_response_text(message: Message, state: FSMContext, **data) -> None:
    response = message.text.strip()
    if len(response) < 1:
        await message.answer("Javob matni bo'sh bo'lmasligi kerak. Qaytadan kiriting:")
        return
    await state.update_data(mb_new_response=response)
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    await state.set_state(MenuBuilderStates.add_button_row)
    await message.answer(
        "Qaysi qatorga joylashtirish?",
        reply_markup=_row_keyboard(len(rows)),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.add_button_row),
    F.data.startswith("mb:row:"),
)
async def handle_add_row_select(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    row_idx = int(callback.data.replace("mb:row:", ""))
    fsm_data = await state.get_data()
    rows: list[list[dict]] = copy.deepcopy(fsm_data.get("mb_rows", []))

    new_btn: dict[str, str] = {"text": fsm_data["mb_new_text"], "type": fsm_data["mb_new_type"]}
    if fsm_data["mb_new_type"] == "action":
        new_btn["action"] = fsm_data.get("mb_new_action", "")
    else:
        new_btn["response"] = fsm_data.get("mb_new_response", "")

    if row_idx >= len(rows):
        rows.append([new_btn])
    else:
        if len(rows[row_idx]) >= 3:
            await callback.message.answer("Qatorda 3 tadan ortiq tugma bo'lmaydi. Boshqa qator tanlang:",
                                          reply_markup=_row_keyboard(len(rows)))
            return
        rows[row_idx].append(new_btn)

    await state.update_data(mb_rows=rows)
    await state.set_state(MenuBuilderStates.viewing)
    await callback.message.answer("Tugma qo'shildi!")
    await _show_menu_view(callback, state)


# ── EDIT button flow ─────────────────────────────────────────────────────────

@router.callback_query(StateFilter(MenuBuilderStates.viewing), F.data == "mb:edit")
async def handle_edit_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    flat = _flat_buttons(rows)
    if not flat:
        await callback.message.answer("Menyu bo'sh. Avval tugma qo'shing.")
        return
    await state.set_state(MenuBuilderStates.edit_select)
    preview = _render_menu_preview(rows)
    await callback.message.answer(
        f"{preview}\n\nTahrirlash uchun tugma raqamini tanlang:",
        reply_markup=_number_keyboard(len(flat), "esel"),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.edit_select),
    F.data.startswith("mb:esel:"),
)
async def handle_edit_select(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    idx = int(callback.data.replace("mb:esel:", ""))
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    flat = _flat_buttons(rows)
    if idx >= len(flat):
        await callback.message.answer("Noto'g'ri raqam.")
        return
    r_idx, c_idx, btn = flat[idx]
    await state.update_data(mb_edit_r=r_idx, mb_edit_c=c_idx)
    await state.set_state(MenuBuilderStates.edit_field)

    current = btn.get("text", "?")
    await callback.message.answer(
        f"Hozirgi matn: {current}\n\nNima o'zgartirmoqchisiz?",
        reply_markup=_edit_field_keyboard(),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.edit_field),
    F.data == "mb:efield:text",
)
async def handle_edit_field_text(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.set_state(MenuBuilderStates.edit_value)
    await callback.message.answer("Yangi matnni kiriting:")


@router.message(
    StateFilter(MenuBuilderStates.edit_value),
    F.text, ~F.text.startswith("/"),
)
async def handle_edit_value(message: Message, state: FSMContext, **data) -> None:
    new_text = message.text.strip()
    if len(new_text) < 1 or len(new_text) > 64:
        await message.answer("Matn 1 dan 64 belgigacha. Qaytadan kiriting:")
        return

    fsm_data = await state.get_data()
    rows: list[list[dict]] = copy.deepcopy(fsm_data.get("mb_rows", []))
    r_idx = fsm_data["mb_edit_r"]
    c_idx = fsm_data["mb_edit_c"]

    if r_idx < len(rows) and c_idx < len(rows[r_idx]):
        rows[r_idx][c_idx]["text"] = new_text

    await state.update_data(mb_rows=rows)
    await state.set_state(MenuBuilderStates.viewing)
    await message.answer("Tugma matni yangilandi!")
    await _show_menu_view(message, state)


# ── DELETE button flow ───────────────────────────────────────────────────────

@router.callback_query(StateFilter(MenuBuilderStates.viewing), F.data == "mb:delete")
async def handle_delete_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    flat = _flat_buttons(rows)
    if not flat:
        await callback.message.answer("Menyu bo'sh.")
        return
    await state.set_state(MenuBuilderStates.delete_select)
    preview = _render_menu_preview(rows)
    await callback.message.answer(
        f"{preview}\n\nO'chirish uchun tugma raqamini tanlang:",
        reply_markup=_number_keyboard(len(flat), "dsel"),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.delete_select),
    F.data.startswith("mb:dsel:"),
)
async def handle_delete_select(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    idx = int(callback.data.replace("mb:dsel:", ""))
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    flat = _flat_buttons(rows)
    if idx >= len(flat):
        await callback.message.answer("Noto'g'ri raqam.")
        return
    r_idx, c_idx, btn = flat[idx]
    await state.update_data(mb_del_r=r_idx, mb_del_c=c_idx)
    await state.set_state(MenuBuilderStates.delete_confirm)
    await callback.message.answer(
        f"'{btn.get('text', '?')}' tugmasini o'chirmoqchimisiz?",
        reply_markup=_confirm_delete_keyboard(),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.delete_confirm),
    F.data == "mb:delconfirm:yes",
)
async def handle_delete_confirm_yes(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    fsm_data = await state.get_data()
    rows: list[list[dict]] = copy.deepcopy(fsm_data.get("mb_rows", []))
    r_idx = fsm_data["mb_del_r"]
    c_idx = fsm_data["mb_del_c"]

    if r_idx < len(rows) and c_idx < len(rows[r_idx]):
        rows[r_idx].pop(c_idx)
        # Remove empty rows
        rows = [row for row in rows if row]

    await state.update_data(mb_rows=rows)
    await state.set_state(MenuBuilderStates.viewing)
    await callback.message.answer("Tugma o'chirildi!")
    await _show_menu_view(callback, state)


@router.callback_query(
    StateFilter(MenuBuilderStates.delete_confirm),
    F.data == "mb:delconfirm:no",
)
async def handle_delete_confirm_no(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.set_state(MenuBuilderStates.viewing)
    await _show_menu_view(callback, state)


# ── REORDER flow ─────────────────────────────────────────────────────────────

@router.callback_query(StateFilter(MenuBuilderStates.viewing), F.data == "mb:reorder")
async def handle_reorder_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    if len(rows) < 2:
        await callback.message.answer("Tartibni o'zgartirish uchun kamida 2 qator kerak.")
        return
    await state.set_state(MenuBuilderStates.reorder_select)
    preview = _render_menu_preview(rows)
    await callback.message.answer(
        f"{preview}\n\nKo'chirish uchun qator raqamini tanlang:",
        reply_markup=_number_keyboard(len(rows), "rsel"),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.reorder_select),
    F.data.startswith("mb:rsel:"),
)
async def handle_reorder_select(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    idx = int(callback.data.replace("mb:rsel:", ""))
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    if idx >= len(rows):
        await callback.message.answer("Noto'g'ri raqam.")
        return
    await state.update_data(mb_reorder_idx=idx)
    await state.set_state(MenuBuilderStates.reorder_direction)
    await callback.message.answer(
        f"Qator {idx + 1}ni qaysi tomonga ko'chirish?",
        reply_markup=_direction_keyboard(),
    )


@router.callback_query(
    StateFilter(MenuBuilderStates.reorder_direction),
    F.data.startswith("mb:dir:"),
)
async def handle_reorder_direction(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    direction = callback.data.replace("mb:dir:", "")
    fsm_data = await state.get_data()
    rows: list[list[dict]] = copy.deepcopy(fsm_data.get("mb_rows", []))
    idx = fsm_data["mb_reorder_idx"]

    if direction == "up" and idx > 0:
        rows[idx], rows[idx - 1] = rows[idx - 1], rows[idx]
    elif direction == "down" and idx < len(rows) - 1:
        rows[idx], rows[idx + 1] = rows[idx + 1], rows[idx]
    else:
        await callback.message.answer("Bu tomonga ko'chirib bo'lmaydi.")
        await state.set_state(MenuBuilderStates.viewing)
        await _show_menu_view(callback, state)
        return

    await state.update_data(mb_rows=rows)
    await state.set_state(MenuBuilderStates.viewing)
    await callback.message.answer("Tartib o'zgartirildi!")
    await _show_menu_view(callback, state)


# ── RESTORE default ──────────────────────────────────────────────────────────

@router.callback_query(StateFilter(MenuBuilderStates.viewing), F.data == "mb:restore")
async def handle_restore(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)

    if not tenant:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    # Try to find the template for this tenant's business type
    from shared.templates.business_templates import BusinessType, get_template
    try:
        # The slug was stored during onboarding; try to match business_type
        # We need to find the original business type - check all templates
        default_menu = None
        for btype in BusinessType:
            template = get_template(btype)
            if template.menu_config:
                default_menu = template.menu_config
                # Simple heuristic: use ceiling as default fallback
                break
        if not default_menu:
            default_menu = {"buttons": [], "admin_buttons": [["📣 Rassilka"]]}
    except Exception:
        default_menu = {"buttons": [], "admin_buttons": [["📣 Rassilka"]]}

    rows = _normalize_menu_config(default_menu)
    admin_buttons = default_menu.get("admin_buttons")
    await state.update_data(mb_rows=rows, mb_admin_buttons=admin_buttons)
    await callback.message.answer("Menyu shablon holatiga qaytarildi!")
    await _show_menu_view(callback, state)


# ── DONE — save to DB ───────────────────────────────────────────────────────

@router.callback_query(StateFilter(MenuBuilderStates.viewing), F.data == "mb:done")
async def handle_done(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    fsm_data = await state.get_data()
    rows = fsm_data.get("mb_rows", [])
    admin_buttons = fsm_data.get("mb_admin_buttons")

    ok = await _save_menu(user_id, rows, admin_buttons)
    await state.clear()

    if ok:
        menu_config = _build_menu_config(rows, admin_buttons)
        await callback.message.answer(
            "Menyu saqlandi!",
            reply_markup=main_menu_keyboard(menu_config=menu_config),
        )
    else:
        await callback.message.answer(
            "Xatolik yuz berdi. Qaytadan urinib ko'ring: /edit_menu",
            reply_markup=main_menu_keyboard(),
        )
