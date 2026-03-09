"""
apps.bot.handlers.private.onboarding
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SaaS tenant onboarding wizard — guided FSM flow in private chat.

FSM flow
--------
  /create_business
    -> business_name -> slug -> business_type (inline KB)
    -> bot_token -> bot_username
    -> admin_group_id (skip OK) -> main_group_id (skip OK)
    -> ai_prompt_choice (default/custom) -> knowledge_base_choice
    -> menu_config_choice -> confirmation -> CREATE tenant

  /my_business — read-only view of the user's tenant config.

All inline callbacks use the ``onb:`` prefix.
"""
from __future__ import annotations

import json
import re

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
from apps.bot.states.onboarding import OnboardingStates
from infrastructure.database.models.tenant import TenantModel
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_tenant_service
from shared.config import get_settings
from shared.logging import get_logger
from shared.templates.business_templates import (
    BusinessType,
    get_ceiling_defaults,
    get_template,
    resolve_template_text,
)
from shared.utils.slugify import generate_slug
from shared.utils.validators import is_valid_bot_token, is_valid_group_id

log = get_logger(__name__)
router = Router(name="private:onboarding")

# ── Helpers ───────────────────────────────────────────────────────────────────

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")


def _safe_business_type(value: str) -> BusinessType:
    """Parse BusinessType with fallback to OTHER for unknown values."""
    try:
        return BusinessType(value)
    except ValueError:
        return BusinessType.OTHER

_SKIP_TEXT = "O'tkazib yuborish"


def _mask_token(token: str) -> str:
    """Show only first 4 and last 4 chars of a bot token."""
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def _type_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for business type selection."""
    types = [
        ("Natyajnoy potolok", "onb:type:ceiling"),
        ("Restoran", "onb:type:restaurant"),
        ("Avtoservis", "onb:type:auto_service"),
        ("Klinika", "onb:type:clinic"),
        ("Boshqa", "onb:type:other"),
    ]
    rows = []
    for i in range(0, len(types), 2):
        row = [InlineKeyboardButton(text=t[0], callback_data=t[1]) for t in types[i:i + 2]]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _choice_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Default / Custom choice keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Shablon (tayyor)", callback_data=f"onb:{prefix}:default"),
            InlineKeyboardButton(text="O'zimniki", callback_data=f"onb:{prefix}:custom"),
        ],
    ])


def _ai_choice_keyboard() -> InlineKeyboardMarkup:
    """AI prompt: Default / Auto Generate / Custom (3 options)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Shablon (tayyor)", callback_data="onb:ai:default")],
        [InlineKeyboardButton(text="Avtomatik yaratish", callback_data="onb:ai:generate")],
        [InlineKeyboardButton(text="O'zimniki", callback_data="onb:ai:custom")],
    ])


def _tone_keyboard() -> InlineKeyboardMarkup:
    """Tone selection for auto-generated prompt."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Professional", callback_data="onb:tone:professional"),
            InlineKeyboardButton(text="Do'stona", callback_data="onb:tone:friendly"),
            InlineKeyboardButton(text="Rasmiy", callback_data="onb:tone:formal"),
        ],
    ])


def _gen_preview_keyboard() -> InlineKeyboardMarkup:
    """Accept / Retry generated prompt."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Qabul qilish", callback_data="onb:gen:accept"),
            InlineKeyboardButton(text="Qayta yaratish", callback_data="onb:gen:retry"),
        ],
    ])


def _my_business_keyboard() -> InlineKeyboardMarkup:
    """Inline action buttons shown on /my_business."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="AI promptni tahrirlash", callback_data="onb:edit:ai_prompt")],
        [InlineKeyboardButton(text="Menyuni tahrirlash", callback_data="onb:edit:menu")],
        [InlineKeyboardButton(text="Lidlar dashboard", callback_data="onb:edit:leads")],
    ])


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Tasdiqlash", callback_data="onb:confirm"),
            InlineKeyboardButton(text="Bekor qilish", callback_data="onb:cancel"),
        ],
    ])


def _slug_keyboard(slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Qabul qilish: {slug}", callback_data="onb:accept_slug")],
    ])


def _build_summary(data: dict) -> str:
    """Build a formatted summary of the onboarding data."""
    btype = data.get("business_type_label", data.get("business_type", "—"))
    token_display = _mask_token(data["bot_token"]) if data.get("bot_token") else "—"
    admin_gid = data.get("admin_group_id") or "(o'tkazildi)"
    main_gid = data.get("main_group_id") or "(o'tkazildi)"

    ai_source = "shablon" if data.get("ai_prompt_is_default") else "maxsus"
    kb_source = "shablon" if data.get("kb_is_default") else "maxsus"
    menu_source = "shablon" if data.get("menu_is_default") else "maxsus"

    return (
        "Biznes sozlamalari:\n\n"
        f"Nomi: {data.get('business_name', '—')}\n"
        f"Slug: {data.get('slug', '—')}\n"
        f"Turi: {btype}\n"
        f"Bot token: {token_display}\n"
        f"Bot username: @{data.get('bot_username', '—')}\n"
        f"Admin guruh: {admin_gid}\n"
        f"Asosiy guruh: {main_gid}\n"
        f"AI prompt: ({ai_source})\n"
        f"Bilimlar bazasi: ({kb_source})\n"
        f"Menyu: ({menu_source})\n"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

@router.message(Command("create_business"), F.chat.type == "private")
async def cmd_create_business(message: Message, state: FSMContext, **data) -> None:
    """Start the tenant onboarding wizard."""
    user_id = message.from_user.id

    # Check if user already owns a tenant
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        existing = await svc.get_by_admin_user(user_id)
        if existing:
            await message.answer(
                f"Sizda allaqachon biznes mavjud: {existing.name}\n"
                "Sozlamalarni ko'rish uchun /my_business buyrug'ini yuboring.",
            )
            return

    await state.clear()
    await state.set_state(OnboardingStates.business_name)
    await message.answer(
        "Biznesingizni sozlashni boshlaymiz!\n\n"
        "Biznesingiz nomini kiriting:"
    )


# ── Step 1: Business name ────────────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.business_name),
    F.text, ~F.text.startswith("/"),
)
async def handle_business_name(message: Message, state: FSMContext, **data) -> None:
    name = message.text.strip()
    if len(name) < 2 or len(name) > 256:
        await message.answer("Nom 2 dan 256 belgigacha bo'lishi kerak. Qaytadan kiriting:")
        return

    slug = generate_slug(name)
    if not slug:
        await message.answer("Nomdan slug yaratib bo'lmadi. Boshqa nom kiriting:")
        return

    await state.update_data(business_name=name, slug=slug)
    await state.set_state(OnboardingStates.slug)
    await message.answer(
        f"Biznes nomi: {name}\n\n"
        f"Avtomatik slug: `{slug}`\n\n"
        "Qabul qilasizmi yoki o'zingizni slug kiriting:",
        reply_markup=_slug_keyboard(slug),
        parse_mode="Markdown",
    )


# ── Step 2: Slug ─────────────────────────────────────────────────────────────

@router.callback_query(StateFilter(OnboardingStates.slug), F.data == "onb:accept_slug")
async def handle_slug_accept(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await state.set_state(OnboardingStates.business_type)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Biznes turini tanlang:",
        reply_markup=_type_keyboard(),
    )


@router.message(
    StateFilter(OnboardingStates.slug),
    F.text, ~F.text.startswith("/"),
)
async def handle_slug_custom(message: Message, state: FSMContext, **data) -> None:
    slug = generate_slug(message.text.strip())
    if not slug or len(slug) < 3 or len(slug) > 64:
        await message.answer(
            "Slug 3 dan 64 belgigacha, faqat lotin harflar, raqamlar va chiziqcha.\n"
            "Qaytadan kiriting:"
        )
        return

    # Check uniqueness
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        if await svc.slug_exists(slug):
            await message.answer(
                f"Slug `{slug}` allaqachon band. Boshqa slug kiriting:",
                parse_mode="Markdown",
            )
            return

    await state.update_data(slug=slug)
    await state.set_state(OnboardingStates.business_type)
    await message.answer(
        "Biznes turini tanlang:",
        reply_markup=_type_keyboard(),
    )


# ── Step 3: Business type ────────────────────────────────────────────────────

@router.callback_query(
    StateFilter(OnboardingStates.business_type),
    F.data.startswith("onb:type:"),
)
async def handle_business_type(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    type_str = callback.data.replace("onb:type:", "")
    try:
        btype = BusinessType(type_str)
    except ValueError:
        await callback.message.answer("Noto'g'ri tanlov. Qaytadan tanlang:", reply_markup=_type_keyboard())
        return

    template = get_template(btype)
    await state.update_data(
        business_type=btype.value,
        business_type_label=template.label,
        template_menu_config=template.menu_config,
        template_ai_prompt=template.ai_system_prompt,
        template_kb=template.knowledge_base,
    )
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(OnboardingStates.bot_token)
    await callback.message.answer(
        f"Tur: {template.label}\n\n"
        "Endi bot tokenini kiriting.\n"
        "(@BotFather dan olgan tokeningiz, masalan: `123456789:ABCdef...`)\n\n"
        "Xavfsizlik uchun xabaringiz avtomatik o'chiriladi.",
        parse_mode="Markdown",
    )


# ── Step 4: Bot token ────────────────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.bot_token),
    F.text, ~F.text.startswith("/"),
)
async def handle_bot_token(message: Message, state: FSMContext, **data) -> None:
    token = message.text.strip()

    # Delete the message containing the token for security
    try:
        await message.delete()
    except Exception:
        pass

    if not is_valid_bot_token(token):
        await message.answer(
            "Token formati noto'g'ri.\n"
            "To'g'ri format: `123456789:ABCdefGhi-JKLmnoPQR_stuvWXyz12345`\n\n"
            "Qaytadan kiriting:",
            parse_mode="Markdown",
        )
        return

    await state.update_data(bot_token=token)
    await state.set_state(OnboardingStates.bot_username)
    await message.answer(
        f"Token qabul qilindi: {_mask_token(token)}\n\n"
        "Botingizning username'ini kiriting (masalan: mybizbot yoki @mybizbot):"
    )


# ── Step 5: Bot username ─────────────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.bot_username),
    F.text, ~F.text.startswith("/"),
)
async def handle_bot_username(message: Message, state: FSMContext, **data) -> None:
    username = message.text.strip().lstrip("@")

    if not _USERNAME_RE.match(username):
        await message.answer(
            "Username 5-32 belgi, faqat lotin harflar, raqamlar va pastki chiziq.\n"
            "Qaytadan kiriting:"
        )
        return

    if not username.lower().endswith("bot"):
        await message.answer(
            "Telegram bot username'i 'bot' bilan tugashi kerak.\n"
            "Qaytadan kiriting:"
        )
        return

    await state.update_data(bot_username=username)
    await state.set_state(OnboardingStates.admin_group_id)
    await message.answer(
        "Admin guruh ID sini kiriting (manfiy raqam, masalan: -1001234567890).\n\n"
        f"Hozircha o'tkazib yuborish uchun \"{_SKIP_TEXT}\" deb yozing:"
    )


# ── Step 6: Admin group ID ───────────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.admin_group_id),
    F.text, ~F.text.startswith("/"),
)
async def handle_admin_group_id(message: Message, state: FSMContext, **data) -> None:
    text = message.text.strip()

    if text.lower() == _SKIP_TEXT.lower() or text.lower() in ("skip", "o'tkazish"):
        await state.update_data(admin_group_id=None)
    elif is_valid_group_id(text):
        await state.update_data(admin_group_id=int(text))
    else:
        await message.answer(
            "Noto'g'ri format. Guruh ID manfiy raqam bo'lishi kerak.\n"
            f"Qaytadan kiriting yoki \"{_SKIP_TEXT}\" deb yozing:"
        )
        return

    await state.set_state(OnboardingStates.main_group_id)
    await message.answer(
        "Asosiy (mijozlar) guruh ID sini kiriting.\n\n"
        f"O'tkazib yuborish uchun \"{_SKIP_TEXT}\" deb yozing:"
    )


# ── Step 7: Main group ID ────────────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.main_group_id),
    F.text, ~F.text.startswith("/"),
)
async def handle_main_group_id(message: Message, state: FSMContext, **data) -> None:
    text = message.text.strip()

    if text.lower() == _SKIP_TEXT.lower() or text.lower() in ("skip", "o'tkazish"):
        await state.update_data(main_group_id=None)
    elif is_valid_group_id(text):
        await state.update_data(main_group_id=int(text))
    else:
        await message.answer(
            "Noto'g'ri format. Guruh ID manfiy raqam bo'lishi kerak.\n"
            f"Qaytadan kiriting yoki \"{_SKIP_TEXT}\" deb yozing:"
        )
        return

    await state.set_state(OnboardingStates.ai_prompt_choice)
    await message.answer(
        "AI tizim promptini sozlash:\n\n"
        "Shablon, avtomatik yaratish yoki o'zingizni kiritish mumkin.",
        reply_markup=_ai_choice_keyboard(),
    )


# ── Step 8: AI prompt choice ─────────────────────────────────────────────────

@router.callback_query(
    StateFilter(OnboardingStates.ai_prompt_choice),
    F.data == "onb:ai:default",
)
async def handle_ai_prompt_default(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    btype = _safe_business_type(fsm_data["business_type"])
    business_name = fsm_data["business_name"]

    if btype == BusinessType.CEILING:
        prompt, _ = get_ceiling_defaults()
    else:
        template = get_template(btype)
        prompt = resolve_template_text(template.ai_system_prompt, business_name)

    await state.update_data(ai_system_prompt=prompt, ai_prompt_is_default=True)

    # Edit mode: save directly to tenant and exit
    if fsm_data.get("is_edit_mode"):
        user_id = callback.from_user.id
        try:
            factory = get_session_factory()
            async with factory() as session:
                svc = get_tenant_service(session)
                await svc.update_tenant_field(user_id, ai_system_prompt=prompt)
                await session.commit()
            await state.clear()
            await callback.message.answer("AI prompt muvaffaqiyatli yangilandi!")
        except Exception:
            log.exception("edit_ai_prompt_failed", user_id=user_id)
            await state.clear()
            await callback.message.answer("Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    await state.set_state(OnboardingStates.knowledge_base_choice)
    await callback.message.answer(
        "AI prompt shablon asosida sozlandi.\n\n"
        "Bilimlar bazasini sozlash:",
        reply_markup=_choice_keyboard("kb"),
    )


@router.callback_query(
    StateFilter(OnboardingStates.ai_prompt_choice),
    F.data == "onb:ai:custom",
)
async def handle_ai_prompt_custom_choice(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(OnboardingStates.ai_prompt_custom)
    await callback.message.answer(
        "O'zingizning AI tizim promptingizni kiriting.\n"
        "(Kamida 50 belgi bo'lishi kerak):"
    )


# ── Step 8a: AI prompt custom ────────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.ai_prompt_custom),
    F.text, ~F.text.startswith("/"),
)
async def handle_ai_prompt_custom(message: Message, state: FSMContext, **data) -> None:
    text = message.text.strip()
    if len(text) < 50:
        await message.answer("Prompt kamida 50 belgi bo'lishi kerak. Qaytadan kiriting:")
        return

    await state.update_data(ai_system_prompt=text, ai_prompt_is_default=False)

    # Edit mode: save directly to tenant and exit
    fsm_data = await state.get_data()
    if fsm_data.get("is_edit_mode"):
        user_id = message.from_user.id
        try:
            factory = get_session_factory()
            async with factory() as session:
                svc = get_tenant_service(session)
                await svc.update_tenant_field(user_id, ai_system_prompt=text)
                await session.commit()
            await state.clear()
            await message.answer("AI prompt muvaffaqiyatli yangilandi!")
        except Exception:
            log.exception("edit_ai_prompt_failed", user_id=user_id)
            await state.clear()
            await message.answer("Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    await state.set_state(OnboardingStates.knowledge_base_choice)
    await message.answer(
        "AI prompt saqlandi.\n\n"
        "Bilimlar bazasini sozlash:",
        reply_markup=_choice_keyboard("kb"),
    )


# ── Step 8b: Auto-generate prompt sub-flow ────────────────────────────────────

@router.callback_query(
    StateFilter(OnboardingStates.ai_prompt_choice),
    F.data == "onb:ai:generate",
)
async def handle_ai_prompt_generate(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(OnboardingStates.ai_gen_description)
    await callback.message.answer(
        "Biznesingizni 1-3 jumlada ta'riflang.\n"
        "(Masalan: Qashqadaryoda natyajnoy potolok o'rnatish xizmati. "
        "6 yillik tajriba, 15 yillik kafolat.)"
    )


@router.message(
    StateFilter(OnboardingStates.ai_gen_description),
    F.text, ~F.text.startswith("/"),
)
async def handle_ai_gen_description(message: Message, state: FSMContext, **data) -> None:
    desc = message.text.strip()
    if len(desc) < 10:
        await message.answer("Ta'rif kamida 10 belgi bo'lishi kerak. Qaytadan kiriting:")
        return
    await state.update_data(gen_description=desc)
    await state.set_state(OnboardingStates.ai_gen_audience)
    await message.answer(
        "Maqsadli auditoriyangiz kimlar?\n"
        "(Masalan: Yoshlar va oilalar, uy qurayotganlar)"
    )


@router.message(
    StateFilter(OnboardingStates.ai_gen_audience),
    F.text, ~F.text.startswith("/"),
)
async def handle_ai_gen_audience(message: Message, state: FSMContext, **data) -> None:
    audience = message.text.strip()
    if len(audience) < 3:
        await message.answer("Kamida 3 belgi kiriting:")
        return
    await state.update_data(gen_audience=audience)
    await state.set_state(OnboardingStates.ai_gen_tone)
    await message.answer(
        "Bot qanday ohangda gaplashsin?",
        reply_markup=_tone_keyboard(),
    )


@router.callback_query(
    StateFilter(OnboardingStates.ai_gen_tone),
    F.data.startswith("onb:tone:"),
)
async def handle_ai_gen_tone(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    tone = callback.data.replace("onb:tone:", "")
    fsm_data = await state.get_data()

    from core.services.prompt_generator_service import PromptInputs, generate_prompt

    inputs = PromptInputs(
        business_name=fsm_data["business_name"],
        business_type=_safe_business_type(fsm_data["business_type"]),
        description=fsm_data["gen_description"],
        target_audience=fsm_data["gen_audience"],
        tone=tone,
    )
    generated = generate_prompt(inputs)

    await state.update_data(ai_system_prompt=generated, ai_prompt_is_default=False)
    await state.set_state(OnboardingStates.ai_gen_preview)

    # Truncate for Telegram's 4096 char limit
    preview = generated[:3000] + "\n\n..." if len(generated) > 3000 else generated
    await callback.message.answer(
        f"Yaratilgan AI prompt:\n\n<pre>{preview}</pre>\n\n"
        "Qabul qilasizmi?",
        reply_markup=_gen_preview_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(
    StateFilter(OnboardingStates.ai_gen_preview),
    F.data == "onb:gen:accept",
)
async def handle_gen_accept(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()

    # Edit mode: save directly to tenant and exit
    if fsm_data.get("is_edit_mode"):
        user_id = callback.from_user.id
        try:
            factory = get_session_factory()
            async with factory() as session:
                svc = get_tenant_service(session)
                await svc.update_tenant_field(
                    user_id, ai_system_prompt=fsm_data["ai_system_prompt"],
                )
                await session.commit()
            await state.clear()
            await callback.message.answer("AI prompt muvaffaqiyatli yangilandi!")
        except Exception:
            log.exception("edit_ai_prompt_failed", user_id=user_id)
            await state.clear()
            await callback.message.answer("Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        return

    await state.set_state(OnboardingStates.knowledge_base_choice)
    await callback.message.answer(
        "AI prompt saqlandi.\n\n"
        "Bilimlar bazasini sozlash:",
        reply_markup=_choice_keyboard("kb"),
    )


@router.callback_query(
    StateFilter(OnboardingStates.ai_gen_preview),
    F.data == "onb:gen:retry",
)
async def handle_gen_retry(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(OnboardingStates.ai_gen_description)
    await callback.message.answer(
        "Biznesingizni qaytadan ta'riflang:"
    )


# ── Step 9: Knowledge base choice ────────────────────────────────────────────

@router.callback_query(
    StateFilter(OnboardingStates.knowledge_base_choice),
    F.data == "onb:kb:default",
)
async def handle_kb_default(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    btype = _safe_business_type(fsm_data["business_type"])
    business_name = fsm_data["business_name"]

    if btype == BusinessType.CEILING:
        _, kb = get_ceiling_defaults()
    else:
        template = get_template(btype)
        kb = resolve_template_text(template.knowledge_base, business_name)

    await state.update_data(knowledge_base=kb, kb_is_default=True)
    await state.set_state(OnboardingStates.menu_config_choice)
    await callback.message.answer(
        "Bilimlar bazasi shablon asosida sozlandi.\n\n"
        "Menyu tugmalarini sozlash:",
        reply_markup=_choice_keyboard("menu"),
    )


@router.callback_query(
    StateFilter(OnboardingStates.knowledge_base_choice),
    F.data == "onb:kb:custom",
)
async def handle_kb_custom_choice(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(OnboardingStates.knowledge_base_custom)
    await callback.message.answer(
        "O'zingizning bilimlar bazangizni kiriting.\n"
        "(Kamida 20 belgi bo'lishi kerak):"
    )


# ── Step 9a: Knowledge base custom ───────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.knowledge_base_custom),
    F.text, ~F.text.startswith("/"),
)
async def handle_kb_custom(message: Message, state: FSMContext, **data) -> None:
    text = message.text.strip()
    if len(text) < 20:
        await message.answer("Bilimlar bazasi kamida 20 belgi bo'lishi kerak. Qaytadan kiriting:")
        return

    await state.update_data(knowledge_base=text, kb_is_default=False)
    await state.set_state(OnboardingStates.menu_config_choice)
    await message.answer(
        "Bilimlar bazasi saqlandi.\n\n"
        "Menyu tugmalarini sozlash:",
        reply_markup=_choice_keyboard("menu"),
    )


# ── Step 10: Menu config choice ──────────────────────────────────────────────

@router.callback_query(
    StateFilter(OnboardingStates.menu_config_choice),
    F.data == "onb:menu:default",
)
async def handle_menu_default(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    menu = fsm_data.get("template_menu_config", {})
    await state.update_data(menu_config=menu, menu_is_default=True)

    await state.set_state(OnboardingStates.confirmation)
    updated_data = await state.get_data()
    await callback.message.answer(
        _build_summary(updated_data),
        reply_markup=_confirm_keyboard(),
    )


@router.callback_query(
    StateFilter(OnboardingStates.menu_config_choice),
    F.data == "onb:menu:custom",
)
async def handle_menu_custom_choice(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(OnboardingStates.menu_config_custom)
    await callback.message.answer(
        "Menyu konfiguratsiyasini JSON formatda kiriting.\n\n"
        'Misol:\n```json\n{\n  "buttons": [\n    ["Xizmatlar", "Narxlar"],\n'
        '    ["Buyurtma", "Operator"]\n  ]\n}\n```',
        parse_mode="Markdown",
    )


# ── Step 10a: Menu config custom ─────────────────────────────────────────────

@router.message(
    StateFilter(OnboardingStates.menu_config_custom),
    F.text, ~F.text.startswith("/"),
)
async def handle_menu_custom(message: Message, state: FSMContext, **data) -> None:
    text = message.text.strip()
    try:
        menu = json.loads(text)
    except json.JSONDecodeError:
        await message.answer("Noto'g'ri JSON format. Qaytadan kiriting:")
        return

    if not isinstance(menu, dict) or "buttons" not in menu:
        await message.answer(
            'JSON da "buttons" kaliti bo\'lishi kerak. Qaytadan kiriting:'
        )
        return

    buttons = menu["buttons"]
    if not isinstance(buttons, list) or not all(isinstance(row, list) for row in buttons):
        await message.answer(
            '"buttons" — ichki ro\'yxatlar ro\'yxati bo\'lishi kerak. Qaytadan kiriting:'
        )
        return

    await state.update_data(menu_config=menu, menu_is_default=False)
    await state.set_state(OnboardingStates.confirmation)
    updated_data = await state.get_data()
    await message.answer(
        _build_summary(updated_data),
        reply_markup=_confirm_keyboard(),
    )


# ── Step 11: Confirmation ────────────────────────────────────────────────────

@router.callback_query(
    StateFilter(OnboardingStates.confirmation),
    F.data == "onb:confirm",
)
async def handle_confirm(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    user_id = callback.from_user.id

    try:
        factory = get_session_factory()
        async with factory() as session:
            from core.services.billing_service import BillingService

            # Encrypt bot token before storing
            _raw_token = fsm_data.get("bot_token")
            _encrypted_token = None
            if _raw_token:
                from core.security.token_encryption import encrypt_token
                _encrypted_token = encrypt_token(_raw_token)

            tenant = TenantModel(
                name=fsm_data["business_name"],
                slug=fsm_data["slug"],
                business_type=fsm_data.get("business_type", "other"),
                bot_token=_encrypted_token,
                bot_username=fsm_data.get("bot_username"),
                admin_group_id=fsm_data.get("admin_group_id"),
                main_group_id=fsm_data.get("main_group_id"),
                admin_user_id=user_id,
                ai_system_prompt=fsm_data.get("ai_system_prompt"),
                knowledge_base=fsm_data.get("knowledge_base"),
                menu_config=fsm_data.get("menu_config", {}),
                is_active=True,
            )
            BillingService(session).initialize_trial(tenant)
            svc = get_tenant_service(session)
            tenant = await svc.create_tenant(tenant)
            await session.commit()

            log.info(
                "onboarding_tenant_created",
                tenant_id=tenant.id,
                slug=tenant.slug,
                admin_user_id=user_id,
            )

            # Auto-connect bot in multi-bot mode
            bot_auto_msg = ""
            settings = get_settings()
            if settings.bot.runtime_mode == "multi" and tenant.bot_token:
                try:
                    from infrastructure.di import get_tenant_bot_service

                    async with factory() as bot_session:
                        bot_svc = get_tenant_bot_service(bot_session)
                        await bot_svc.connect_bot(tenant.id, tenant.bot_token)
                        await bot_session.commit()
                    bot_auto_msg = "\nBot avtomatik ulandi!"
                    log.info(
                        "onboarding_bot_auto_connected",
                        tenant_id=tenant.id,
                        slug=tenant.slug,
                    )
                except Exception:
                    bot_auto_msg = (
                        "\n⚠️ Botni avtomatik ulab bo'lmadi. "
                        "/connect_bot buyrug'i bilan qayta urinib ko'ring."
                    )
                    log.warning(
                        "onboarding_bot_auto_connect_failed",
                        tenant_id=tenant.id,
                        slug=tenant.slug,
                    )

            await state.clear()
            await callback.message.answer(
                f"Biznesingiz muvaffaqiyatli yaratildi!\n\n"
                f"Nomi: {tenant.name}\n"
                f"Slug: {tenant.slug}\n"
                f"ID: {tenant.id}"
                f"{bot_auto_msg}\n\n"
                "Sozlamalarni ko'rish: /my_business",
                reply_markup=main_menu_keyboard(),
            )

    except Exception:
        log.exception("onboarding_tenant_create_failed", user_id=user_id)
        await state.clear()
        await callback.message.answer(
            "Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring: /create_business",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(
    StateFilter(OnboardingStates.confirmation),
    F.data == "onb:cancel",
)
async def handle_cancel(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await callback.message.answer(
        "Biznes yaratish bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


# ── Edit AI prompt from /my_business ──────────────────────────────────────────

@router.callback_query(F.data == "onb:edit:ai_prompt")
async def handle_edit_ai_prompt(callback: CallbackQuery, state: FSMContext, **data) -> None:
    """Enter AI prompt edit flow from /my_business."""
    await callback.answer()
    user_id = callback.from_user.id

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)

    if not tenant:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    await state.clear()
    await state.update_data(
        is_edit_mode=True,
        business_name=tenant.name,
        business_type=tenant.business_type or "other",
    )
    await state.set_state(OnboardingStates.ai_prompt_choice)
    await callback.message.answer(
        "AI tizim promptini yangilash:",
        reply_markup=_ai_choice_keyboard(),
    )


# ── /my_business command ─────────────────────────────────────────────────────

@router.message(Command("my_business"), F.chat.type == "private")
async def cmd_my_business(message: Message, **data) -> None:
    """Show the user's tenant configuration."""
    user_id = message.from_user.id

    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)

    if not tenant:
        await message.answer(
            "Sizda hali biznes yo'q.\n"
            "Yangi biznes yaratish uchun /create_business buyrug'ini yuboring."
        )
        return

    admin_gid = tenant.admin_group_id or "(sozlanmagan)"
    main_gid = tenant.main_group_id or "(sozlanmagan)"
    token_display = _mask_token(tenant.bot_token) if tenant.bot_token else "(sozlanmagan)"
    username = f"@{tenant.bot_username}" if tenant.bot_username else "(sozlanmagan)"
    ai_prompt = f"({len(tenant.ai_system_prompt)} belgi)" if tenant.ai_system_prompt else "(sozlanmagan)"
    kb_display = f"({len(tenant.knowledge_base)} belgi)" if tenant.knowledge_base else "(sozlanmagan)"
    menu_display = "sozlangan" if tenant.menu_config.get("buttons") else "(sozlanmagan)"
    btype_label = _safe_business_type(tenant.business_type or "other").value

    await message.answer(
        f"Biznes sozlamalari:\n\n"
        f"Nomi: {tenant.name}\n"
        f"Slug: {tenant.slug}\n"
        f"Turi: {btype_label}\n"
        f"Holat: {'Faol' if tenant.is_active else 'Nofaol'}\n"
        f"Bot: {username}\n"
        f"Bot token: {token_display}\n"
        f"Admin guruh: {admin_gid}\n"
        f"Asosiy guruh: {main_gid}\n"
        f"AI prompt: {ai_prompt}\n"
        f"Bilimlar bazasi: {kb_display}\n"
        f"Menyu: {menu_display}\n"
        f"\nYaratilgan: {tenant.created_at:%Y-%m-%d %H:%M}",
        reply_markup=_my_business_keyboard(),
    )
