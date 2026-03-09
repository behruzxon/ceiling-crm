"""
apps.bot.handlers.private.knowledge
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In-bot AI Knowledge Base manager for tenant owners.

Entry points:
  /knowledge command (private chat)
  Callback from owner dashboard ("Bilimlar bazasi")

All inline callbacks use the ``kb:`` prefix.
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

from apps.bot.states.knowledge import KnowledgeAddStates, KnowledgeEditStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_ai_knowledge_repo, get_tenant_service
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:knowledge")

# ── Constants ─────────────────────────────────────────────────────────────

_PAGE_SIZE = 5
_TITLE_MAX_LEN = 120
_CONTENT_MAX_LEN = 2000

CATEGORIES = {
    "pricing": "💰 Narxlar",
    "faq": "❓ FAQ",
    "product": "📦 Mahsulot",
    "service": "🔧 Xizmat",
    "promo": "🎁 Aksiya",
    "other": "📝 Boshqa",
}

_CAT_LABELS = list(CATEGORIES.values())
_CAT_KEYS = list(CATEGORIES.keys())


# ── Helpers ────────────────────────────────────────────────────────────────

async def _get_tenant_id(user_id: int) -> int | None:
    """Resolve tenant_id from admin_user_id. Returns None if not an owner."""
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)
    return tenant.id if tenant else None


def _cat_label(key: str) -> str:
    """Get human-readable category label."""
    return CATEGORIES.get(key, key)


def _main_keyboard() -> InlineKeyboardMarkup:
    """Main knowledge management menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Ro'yxat", callback_data="kb:list:all:0"),
            InlineKeyboardButton(text="➕ Qo'shish", callback_data="kb:add"),
        ],
        [
            InlineKeyboardButton(text="📂 Kategoriyalar", callback_data="kb:categories"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="kb:stats"),
        ],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="owndash:back")],
    ])


def _category_filter_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for filtering by category."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in CATEGORIES.items():
        row.append(InlineKeyboardButton(
            text=label, callback_data=f"kb:list:{key}:0",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="kb:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _category_select_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting category when adding entry."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in CATEGORIES.items():
        row.append(InlineKeyboardButton(
            text=label, callback_data=f"kb:cat:{key}",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="kb:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _entry_keyboard(entry_id: int, cat: str, page: int) -> InlineKeyboardMarkup:
    """Keyboard for a single entry detail view."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Tahrirlash", callback_data=f"kb:edit:{entry_id}",
            ),
            InlineKeyboardButton(
                text="🗑 O'chirish", callback_data=f"kb:del:{entry_id}",
            ),
        ],
        [InlineKeyboardButton(
            text="🔙 Ro'yxatga", callback_data=f"kb:list:{cat}:{page}",
        )],
    ])


def _list_keyboard(
    entries: list, page: int, has_next: bool, cat: str,
) -> InlineKeyboardMarkup:
    """List view with entry buttons and pagination."""
    rows: list[list[InlineKeyboardButton]] = []
    for e in entries:
        rows.append([InlineKeyboardButton(
            text=f"{_cat_label(e.category)} {e.title[:40]}",
            callback_data=f"kb:view:{e.id}:{cat}:{page}",
        )])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Oldingi", callback_data=f"kb:list:{cat}:{page - 1}",
        ))
    if has_next:
        nav_row.append(InlineKeyboardButton(
            text="Keyingi ➡️", callback_data=f"kb:list:{cat}:{page + 1}",
        ))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="kb:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _edit_field_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    """Choose which field to edit."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📂 Kategoriya", callback_data=f"kb:editf:{entry_id}:category",
            ),
            InlineKeyboardButton(
                text="📝 Sarlavha", callback_data=f"kb:editf:{entry_id}:title",
            ),
        ],
        [InlineKeyboardButton(
            text="📄 Mazmun", callback_data=f"kb:editf:{entry_id}:content",
        )],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="kb:cancel")],
    ])


def _edit_category_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    """Select new category when editing."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, label in CATEGORIES.items():
        row.append(InlineKeyboardButton(
            text=label, callback_data=f"kb:editcat:{entry_id}:{key}",
        ))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="kb:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_delete_keyboard(entry_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Ha, o'chirish", callback_data=f"kb:confirm_del:{entry_id}",
            ),
            InlineKeyboardButton(
                text="❌ Yo'q", callback_data="kb:main",
            ),
        ],
    ])


# ── Entry points ──────────────────────────────────────────────────────────

@router.message(Command("knowledge"), F.chat.type == "private")
async def cmd_knowledge(message: Message, state: FSMContext, **data) -> None:
    """Entry point: /knowledge command."""
    await state.clear()
    user_id = message.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await message.answer("Siz biznes egasi emassiz.")
        return
    await message.answer(
        "🧠 <b>AI Bilimlar Bazasi</b>\n\n"
        "Bu yerda AI yordamchingiz uchun bilimlar qo'shishingiz mumkin.",
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "kb:main")
async def cb_main(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Return to main knowledge menu."""
    await state.clear()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return
    await callback.message.edit_text(
        "🧠 <b>AI Bilimlar Bazasi</b>\n\n"
        "Bu yerda AI yordamchingiz uchun bilimlar qo'shishingiz mumkin.",
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── List entries ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kb:list:"))
async def cb_list(callback: CallbackQuery, **data) -> None:
    """List entries with pagination. Format: kb:list:{category|all}:{page}."""
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    parts = callback.data.split(":")
    cat = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        if cat == "all":
            all_entries = await repo.get_by_tenant(tenant_id)
        else:
            all_entries = await repo.get_by_tenant_and_category(tenant_id, cat)

    total = len(all_entries)
    start = page * _PAGE_SIZE
    page_entries = all_entries[start : start + _PAGE_SIZE]
    has_next = start + _PAGE_SIZE < total

    if not all_entries:
        label = "Barcha" if cat == "all" else _cat_label(cat)
        await callback.message.edit_text(
            f"📋 <b>{label}</b> — hozircha bo'sh.\n\n"
            "➕ tugmasini bosib bilim qo'shing.",
            reply_markup=_main_keyboard(),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    label = "Barcha" if cat == "all" else _cat_label(cat)
    text = f"📋 <b>{label}</b> ({total} ta)\n\nSahifa {page + 1}:"
    await callback.message.edit_text(
        text,
        reply_markup=_list_keyboard(page_entries, page, has_next, cat),
        parse_mode="HTML",
    )
    await callback.answer()


# ── View single entry ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kb:view:"))
async def cb_view(callback: CallbackQuery, **data) -> None:
    """View a single entry. Format: kb:view:{id}:{cat}:{page}."""
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    parts = callback.data.split(":")
    entry_id = int(parts[2])
    cat = parts[3] if len(parts) > 3 else "all"
    page = int(parts[4]) if len(parts) > 4 else 0

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        all_entries = await repo.get_by_tenant(tenant_id)
        entry = next((e for e in all_entries if e.id == entry_id), None)

    if not entry:
        await callback.answer("Yozuv topilmadi.", show_alert=True)
        return

    text = (
        f"📄 <b>{entry.title}</b>\n\n"
        f"📂 Kategoriya: {_cat_label(entry.category)}\n"
        f"📝 Mazmun:\n{entry.content}\n\n"
        f"🕐 Yaratilgan: {entry.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=_entry_keyboard(entry_id, cat, page),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Category filter ───────────────────────────────────────────────────────

@router.callback_query(F.data == "kb:categories")
async def cb_categories(callback: CallbackQuery, **data) -> None:
    """Show category filter buttons."""
    await callback.message.edit_text(
        "📂 <b>Kategoriya bo'yicha filtrlash:</b>",
        reply_markup=_category_filter_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Stats ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "kb:stats")
async def cb_stats(callback: CallbackQuery, **data) -> None:
    """Show count of entries per category."""
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        all_entries = await repo.get_by_tenant(tenant_id)

    # Count by category
    counts: dict[str, int] = {}
    for e in all_entries:
        counts[e.category] = counts.get(e.category, 0) + 1

    total = len(all_entries)
    lines = [f"📊 <b>Bilimlar statistikasi</b> ({total} ta)\n"]
    for key, label in CATEGORIES.items():
        cnt = counts.get(key, 0)
        if cnt > 0:
            lines.append(f"  {label}: {cnt}")

    if not counts:
        lines.append("  Hozircha bo'sh.")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Add entry flow ────────────────────────────────────────────────────────

@router.callback_query(F.data == "kb:add")
async def cb_add_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Start add flow: select category."""
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    await state.update_data(tenant_id=tenant_id)
    await state.set_state(KnowledgeAddStates.waiting_category)
    await callback.message.edit_text(
        "📂 <b>Kategoriyani tanlang:</b>",
        reply_markup=_category_select_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(
    F.data.startswith("kb:cat:"),
    StateFilter(KnowledgeAddStates.waiting_category),
)
async def cb_add_category_selected(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    """Category selected → ask for title."""
    cat_key = callback.data.split(":")[2]
    if cat_key not in CATEGORIES:
        await callback.answer("Noto'g'ri kategoriya.", show_alert=True)
        return

    await state.update_data(category=cat_key)
    await state.set_state(KnowledgeAddStates.waiting_title)
    await callback.message.edit_text(
        f"📂 Kategoriya: {_cat_label(cat_key)}\n\n"
        f"📝 Sarlavhani yozing (max {_TITLE_MAX_LEN} belgi):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(StateFilter(KnowledgeAddStates.waiting_title))
async def msg_add_title(message: Message, state: FSMContext, **data) -> None:
    """Title entered → validate and ask for content."""
    title = (message.text or "").strip()
    if not title:
        await message.answer("Sarlavha bo'sh bo'lmasligi kerak. Qayta kiriting:")
        return
    if len(title) > _TITLE_MAX_LEN:
        await message.answer(
            f"Sarlavha juda uzun ({len(title)}/{_TITLE_MAX_LEN}). Qisqartiring:",
        )
        return

    await state.update_data(title=title)
    await state.set_state(KnowledgeAddStates.waiting_content)
    await message.answer(
        f"📝 Sarlavha: <b>{title}</b>\n\n"
        f"📄 Mazmunni yozing (max {_CONTENT_MAX_LEN} belgi):",
        parse_mode="HTML",
    )


@router.message(StateFilter(KnowledgeAddStates.waiting_content))
async def msg_add_content(message: Message, state: FSMContext, **data) -> None:
    """Content entered → validate, save, invalidate cache."""
    content = (message.text or "").strip()
    if not content:
        await message.answer("Mazmun bo'sh bo'lmasligi kerak. Qayta kiriting:")
        return
    if len(content) > _CONTENT_MAX_LEN:
        await message.answer(
            f"Mazmun juda uzun ({len(content)}/{_CONTENT_MAX_LEN}). Qisqartiring:",
        )
        return

    fsm_data = await state.get_data()
    tenant_id = fsm_data["tenant_id"]
    category = fsm_data["category"]
    title = fsm_data["title"]

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        entry = await repo.add_entry(tenant_id, category, title, content)
        await session.commit()

    # Invalidate cache
    from core.services.ai_knowledge_service import invalidate_tenant_knowledge_cache
    await invalidate_tenant_knowledge_cache(tenant_id)

    await state.clear()
    await message.answer(
        f"✅ Bilim qo'shildi!\n\n"
        f"📂 {_cat_label(category)}\n"
        f"📝 {title}\n"
        f"📄 {content[:100]}{'...' if len(content) > 100 else ''}",
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )
    log.info("knowledge_added", tenant_id=tenant_id, entry_id=entry.id, category=category)


# ── Edit entry flow ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kb:edit:"))
async def cb_edit_start(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Start edit: choose which field to edit."""
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    entry_id = int(callback.data.split(":")[2])
    await state.update_data(tenant_id=tenant_id, edit_entry_id=entry_id)
    await callback.message.edit_text(
        "✏️ <b>Qaysi maydonni tahrirlash kerak?</b>",
        reply_markup=_edit_field_keyboard(entry_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("kb:editf:"))
async def cb_edit_field_selected(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    """Field selected → ask for new value. Format: kb:editf:{id}:{field}."""
    parts = callback.data.split(":")
    entry_id = int(parts[2])
    field = parts[3]

    if field == "category":
        await state.update_data(edit_entry_id=entry_id, edit_field=field)
        await callback.message.edit_text(
            "📂 <b>Yangi kategoriyani tanlang:</b>",
            reply_markup=_edit_category_keyboard(entry_id),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    field_label = "Sarlavha" if field == "title" else "Mazmun"
    max_len = _TITLE_MAX_LEN if field == "title" else _CONTENT_MAX_LEN

    await state.update_data(edit_entry_id=entry_id, edit_field=field)
    await state.set_state(KnowledgeEditStates.waiting_value)
    await callback.message.edit_text(
        f"✏️ Yangi <b>{field_label}</b>ni yozing (max {max_len} belgi):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("kb:editcat:"))
async def cb_edit_category_selected(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    """Category edit via inline button. Format: kb:editcat:{id}:{cat_key}."""
    parts = callback.data.split(":")
    entry_id = int(parts[2])
    new_cat = parts[3]

    if new_cat not in CATEGORIES:
        await callback.answer("Noto'g'ri kategoriya.", show_alert=True)
        return

    fsm_data = await state.get_data()
    tenant_id = fsm_data.get("tenant_id")
    if not tenant_id:
        tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        updated = await repo.update_entry(entry_id, category=new_cat)
        await session.commit()

    if not updated:
        await callback.answer("Yozuv topilmadi.", show_alert=True)
        return

    from core.services.ai_knowledge_service import invalidate_tenant_knowledge_cache
    await invalidate_tenant_knowledge_cache(tenant_id)

    await state.clear()
    await callback.message.edit_text(
        f"✅ Kategoriya yangilandi: {_cat_label(new_cat)}",
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
    log.info("knowledge_edited", tenant_id=tenant_id, entry_id=entry_id, field="category")


@router.message(StateFilter(KnowledgeEditStates.waiting_value))
async def msg_edit_value(message: Message, state: FSMContext, **data) -> None:
    """New field value entered → validate, update, invalidate cache."""
    value = (message.text or "").strip()
    fsm_data = await state.get_data()
    field = fsm_data["edit_field"]
    entry_id = fsm_data["edit_entry_id"]
    tenant_id = fsm_data.get("tenant_id")

    if not tenant_id:
        tenant_id = await _get_tenant_id(message.from_user.id)
    if not tenant_id:
        await message.answer("Siz biznes egasi emassiz.")
        await state.clear()
        return

    # Validate
    if not value:
        await message.answer("Qiymat bo'sh bo'lmasligi kerak. Qayta kiriting:")
        return

    max_len = _TITLE_MAX_LEN if field == "title" else _CONTENT_MAX_LEN
    if len(value) > max_len:
        await message.answer(
            f"Juda uzun ({len(value)}/{max_len}). Qisqartiring:",
        )
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        updated = await repo.update_entry(entry_id, **{field: value})
        await session.commit()

    if not updated:
        await message.answer("Yozuv topilmadi.", reply_markup=_main_keyboard())
        await state.clear()
        return

    from core.services.ai_knowledge_service import invalidate_tenant_knowledge_cache
    await invalidate_tenant_knowledge_cache(tenant_id)

    await state.clear()
    field_label = "Sarlavha" if field == "title" else "Mazmun"
    await message.answer(
        f"✅ {field_label} yangilandi!",
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )
    log.info("knowledge_edited", tenant_id=tenant_id, entry_id=entry_id, field=field)


# ── Delete entry ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kb:del:"))
async def cb_delete_confirm(callback: CallbackQuery, **data) -> None:
    """Ask for delete confirmation."""
    entry_id = int(callback.data.split(":")[2])
    await callback.message.edit_text(
        "🗑 <b>Haqiqatan ham o'chirmoqchimisiz?</b>",
        reply_markup=_confirm_delete_keyboard(entry_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("kb:confirm_del:"))
async def cb_delete_confirmed(callback: CallbackQuery, **data) -> None:
    """Delete entry after confirmation."""
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.answer("Siz biznes egasi emassiz.", show_alert=True)
        return

    entry_id = int(callback.data.split(":")[2])

    factory = get_session_factory()
    async with factory() as session:
        repo = get_ai_knowledge_repo(session, tenant_id)
        # Verify ownership: entry must belong to this tenant
        all_entries = await repo.get_by_tenant(tenant_id)
        if not any(e.id == entry_id for e in all_entries):
            await callback.answer("Yozuv topilmadi yoki sizga tegishli emas.", show_alert=True)
            return
        deleted = await repo.delete_entry(entry_id)
        await session.commit()

    if deleted:
        from core.services.ai_knowledge_service import invalidate_tenant_knowledge_cache
        await invalidate_tenant_knowledge_cache(tenant_id)

        await callback.message.edit_text(
            "✅ Yozuv o'chirildi.",
            reply_markup=_main_keyboard(),
            parse_mode="HTML",
        )
        log.info("knowledge_deleted", tenant_id=tenant_id, entry_id=entry_id)
    else:
        await callback.answer("O'chirishda xatolik.", show_alert=True)

    await callback.answer()


# ── Cancel FSM ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "kb:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Cancel current FSM flow and return to main menu."""
    await state.clear()
    await callback.message.edit_text(
        "🧠 <b>AI Bilimlar Bazasi</b>\n\n"
        "Bu yerda AI yordamchingiz uchun bilimlar qo'shishingiz mumkin.",
        reply_markup=_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()
