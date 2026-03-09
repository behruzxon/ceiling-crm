"""
apps.bot.handlers.private.auto_onboarding
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Simplified automatic SaaS onboarding wizard.

Triggered from /start when a user has no tenant. Collects company name,
industry type, and bot token in 4 quick steps, then auto-creates tenant
with sensible defaults and starts a 7-day PRO trial.

FSM flow:
  /start (no tenant detected)
    -> company_name -> industry_type (inline KB)
    -> bot_token -> confirmation -> CREATE tenant + connect bot

All inline callbacks use the ``aonb:`` prefix.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.keyboards.main_menu import main_menu_keyboard
from apps.bot.states.auto_onboarding import AutoOnboardingStates
from infrastructure.database.models.tenant import TenantModel
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_tenant_bot_service, get_tenant_service
from shared.config import get_settings
from shared.logging import get_logger
from shared.templates.business_templates import (
    BusinessType,
    get_ceiling_defaults,
    get_template,
    get_welcome_text,
    resolve_template_text,
)
from shared.utils.slugify import generate_slug
from shared.utils.validators import is_valid_bot_token

log = get_logger(__name__)
router = Router(name="private:auto_onboarding")


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mask_token(token: str) -> str:
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"


def _safe_business_type(value: str) -> BusinessType:
    try:
        return BusinessType(value)
    except ValueError:
        return BusinessType.OTHER


def _type_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for industry type selection."""
    types = [
        ("Natyajnoy potolok", "aonb:type:ceiling"),
        ("Restoran", "aonb:type:restaurant"),
        ("Avtoservis", "aonb:type:auto_service"),
        ("Klinika", "aonb:type:clinic"),
        ("Boshqa", "aonb:type:other"),
    ]
    rows = []
    for i in range(0, len(types), 2):
        row = [
            InlineKeyboardButton(text=t[0], callback_data=t[1])
            for t in types[i : i + 2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Tasdiqlash", callback_data="aonb:confirm"),
            InlineKeyboardButton(text="Bekor qilish", callback_data="aonb:cancel"),
        ],
    ])


def _skip_token_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Keyinroq ulash", callback_data="aonb:skip_token",
            ),
        ],
    ])


def _setup_complete_keyboard() -> InlineKeyboardMarkup:
    """Quick action buttons after setup."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="CRM Dashboard", callback_data="aonb:go:leads"),
            InlineKeyboardButton(text="Bilimlar bazasi", callback_data="aonb:go:knowledge"),
        ],
        [
            InlineKeyboardButton(text="AI ni sinash", callback_data="aonb:go:ai"),
            InlineKeyboardButton(text="Bot holati", callback_data="aonb:go:bot_status"),
        ],
        [
            InlineKeyboardButton(text="Obuna ma'lumoti", callback_data="aonb:go:subscription"),
        ],
    ])


def _build_summary(fsm_data: dict) -> str:
    """Build a confirmation summary from FSM data."""
    btype_label = fsm_data.get("business_type_label", fsm_data.get("business_type", "—"))
    token_display = _mask_token(fsm_data["bot_token"]) if fsm_data.get("bot_token") else "(keyinroq)"
    bot_user = fsm_data.get("bot_username")
    bot_display = f"@{bot_user}" if bot_user else "(keyinroq)"

    return (
        "Biznes sozlamalari:\n\n"
        f"Nomi: {fsm_data.get('company_name', '—')}\n"
        f"Turi: {btype_label}\n"
        f"Bot token: {token_display}\n"
        f"Bot: {bot_display}\n\n"
        "Avtomatik sozlanadi:\n"
        "  AI tizim prompti (shablon)\n"
        "  Bilimlar bazasi (shablon)\n"
        "  Menyu tugmalari (shablon)\n"
        "  7 kunlik PRO sinov muddati\n\n"
        "Tasdiqlaysizmi?"
    )


# ── Entry point (called from /start) ────────────────────────────────────────


async def start_auto_onboarding(message: Message, state: FSMContext) -> None:
    """Begin the auto-onboarding flow. Called from the /start handler."""
    user_id = message.from_user.id

    # Double-check: ensure no existing tenant
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        existing = await svc.get_by_admin_user(user_id)
        if existing:
            await message.answer(
                f"Sizda allaqachon biznes mavjud: {existing.name}\n"
                "Sozlamalarni ko'rish: /my_business",
            )
            return

    await state.clear()
    await state.set_state(AutoOnboardingStates.company_name)
    await message.answer(
        "Xush kelibsiz! Keling, biznesingiz uchun bot sozlaymiz.\n\n"
        "1/4  Biznesingiz nomini kiriting:",
    )


# ── Step 1: Company name ────────────────────────────────────────────────────


@router.message(
    StateFilter(AutoOnboardingStates.company_name),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_company_name(message: Message, state: FSMContext, **data) -> None:
    name = message.text.strip()
    if len(name) < 2 or len(name) > 256:
        await message.answer("Nom 2 dan 256 belgigacha bo'lishi kerak. Qaytadan kiriting:")
        return

    slug = generate_slug(name)
    if not slug:
        await message.answer("Nomdan slug yaratib bo'lmadi. Boshqa nom kiriting:")
        return

    # Check slug uniqueness
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        if await svc.slug_exists(slug):
            # Append user_id to make unique
            slug = f"{slug}-{message.from_user.id}"

    await state.update_data(company_name=name, slug=slug)
    await state.set_state(AutoOnboardingStates.industry_type)
    await message.answer(
        f"Biznes nomi: {name}\n\n"
        "2/4  Biznesingiz turini tanlang:",
        reply_markup=_type_keyboard(),
    )


# ── Step 2: Industry type ───────────────────────────────────────────────────


@router.callback_query(
    StateFilter(AutoOnboardingStates.industry_type),
    F.data.startswith("aonb:type:"),
)
async def handle_industry_type(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    await callback.answer()
    type_str = callback.data.replace("aonb:type:", "")

    try:
        btype = BusinessType(type_str)
    except ValueError:
        await callback.message.answer(
            "Noto'g'ri tanlov. Qaytadan tanlang:",
            reply_markup=_type_keyboard(),
        )
        return

    template = get_template(btype)
    await state.update_data(
        business_type=btype.value,
        business_type_label=template.label,
    )
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(AutoOnboardingStates.bot_token)
    await callback.message.answer(
        f"Tur: {template.label}\n\n"
        "3/4  @BotFather dan olgan bot tokenini yuboring.\n"
        "(Masalan: <code>123456789:ABCdef...</code>)\n\n"
        "Xavfsizlik uchun xabaringiz avtomatik o'chiriladi.\n\n"
        "Hozir token yo'qmi? Keyinroq ulashingiz mumkin.",
        reply_markup=_skip_token_keyboard(),
    )


# ── Step 3: Bot token ───────────────────────────────────────────────────────


@router.message(
    StateFilter(AutoOnboardingStates.bot_token),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_bot_token(message: Message, state: FSMContext, **data) -> None:
    token = message.text.strip()

    # Delete message for security
    try:
        await message.delete()
    except Exception:
        pass

    if not is_valid_bot_token(token):
        await message.answer(
            "Token formati noto'g'ri.\n"
            "To'g'ri format: <code>123456789:ABCdefGhi-JKL...</code>\n\n"
            "Qaytadan kiriting yoki keyinroq ulash tugmasini bosing:",
            reply_markup=_skip_token_keyboard(),
        )
        return

    # Validate with Telegram API
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_bot_service(session)
        try:
            bot_info = await svc.validate_token(token)
        except ValueError as exc:
            await message.answer(
                f"Token yaroqsiz: {exc}\nQaytadan kiriting:",
                reply_markup=_skip_token_keyboard(),
            )
            return
        except ConnectionError as exc:
            await message.answer(
                f"Telegram bilan bog'lanib bo'lmadi: {exc}\n"
                "Qaytadan urinib ko'ring:",
                reply_markup=_skip_token_keyboard(),
            )
            return

    await state.update_data(
        bot_token=token,
        bot_username=bot_info.username,
        bot_first_name=bot_info.first_name,
        bot_id=bot_info.bot_id,
    )
    await state.set_state(AutoOnboardingStates.confirmation)

    fsm_data = await state.get_data()
    await message.answer(
        f"Token qabul qilindi: {_mask_token(token)}\n"
        f"Bot: @{bot_info.username or '?'}\n\n"
        "4/4  " + _build_summary(fsm_data),
        reply_markup=_confirm_keyboard(),
    )


@router.callback_query(
    StateFilter(AutoOnboardingStates.bot_token),
    F.data == "aonb:skip_token",
)
async def handle_skip_token(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    await state.update_data(bot_token=None, bot_username=None)
    await state.set_state(AutoOnboardingStates.confirmation)

    fsm_data = await state.get_data()
    await callback.message.answer(
        "Bot tokeni keyinroq ulanadi.\n\n"
        "4/4  " + _build_summary(fsm_data),
        reply_markup=_confirm_keyboard(),
    )


# ── Step 4: Confirmation ────────────────────────────────────────────────────


@router.callback_query(
    StateFilter(AutoOnboardingStates.confirmation),
    F.data == "aonb:confirm",
)
async def handle_confirm(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    fsm_data = await state.get_data()
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name or ""

    try:
        factory = get_session_factory()

        # ── 1. Resolve defaults from template ────────────────────────────
        btype = _safe_business_type(fsm_data.get("business_type", "other"))
        business_name = fsm_data["company_name"]

        if btype == BusinessType.CEILING:
            ai_prompt, knowledge_base = get_ceiling_defaults()
        else:
            template = get_template(btype)
            ai_prompt = resolve_template_text(
                template.ai_system_prompt, business_name,
            )
            knowledge_base = resolve_template_text(
                template.knowledge_base, business_name,
            )

        menu_config = get_template(btype).menu_config

        # ── 2. Create tenant ─────────────────────────────────────────────
        async with factory() as session:
            from core.services.billing_service import BillingService

            # Encrypt bot token before storing
            _raw_token = fsm_data.get("bot_token")
            _encrypted_token = None
            if _raw_token:
                from core.security.token_encryption import encrypt_token
                _encrypted_token = encrypt_token(_raw_token)

            tenant = TenantModel(
                name=business_name,
                slug=fsm_data["slug"],
                business_type=btype.value,
                bot_token=_encrypted_token,
                bot_username=fsm_data.get("bot_username"),
                admin_user_id=user_id,
                ai_system_prompt=ai_prompt,
                knowledge_base=knowledge_base,
                menu_config=menu_config,
                is_active=True,
            )
            BillingService(session).initialize_trial(tenant)
            svc = get_tenant_service(session)
            tenant = await svc.create_tenant(tenant)
            await session.commit()

            tenant_id = tenant.id
            tenant_name = tenant.name

            log.info(
                "auto_onboarding_tenant_created",
                tenant_id=tenant_id,
                slug=tenant.slug,
                business_type=btype.value,
                admin_user_id=user_id,
            )

        # ── 3. Create default knowledge entries ──────────────────────────
        await _seed_default_knowledge(tenant_id, btype, business_name)

        # ── 4. Connect bot (if token provided) ──────────────────────────
        bot_msg = ""
        token = fsm_data.get("bot_token")
        settings = get_settings()

        if token:
            try:
                async with factory() as bot_session:
                    bot_svc = get_tenant_bot_service(bot_session)
                    bot_status = await bot_svc.connect_bot(tenant_id, token)
                    await bot_session.commit()
                bot_msg = f"\nBot ulandi: @{bot_status.bot_username}"
                log.info(
                    "auto_onboarding_bot_connected",
                    tenant_id=tenant_id,
                )
            except Exception:
                bot_msg = (
                    "\nBot ulanmadi. Keyinroq /connect_bot bilan ulang."
                )
                log.warning(
                    "auto_onboarding_bot_connect_failed",
                    tenant_id=tenant_id,
                )
        else:
            bot_msg = "\nBot hali ulanmagan. /connect_bot bilan ulang."

        # ── 5. Build setup summary ───────────────────────────────────────
        await state.clear()

        trial_days = 7
        bot_username = fsm_data.get("bot_username")
        bot_display = f"@{bot_username}" if bot_username else "(ulanmagan)"

        summary = (
            "Tabriklaymiz! Biznesingiz tayyor!\n\n"
            f"Biznes: {tenant_name}\n"
            f"Bot: {bot_display}"
            f"{bot_msg}\n\n"
            f"Obuna: PRO (sinov)\n"
            f"Sinov muddati: {trial_days} kun\n\n"
            "Avtomatik sozlandi:\n"
            "  AI yordamchi (shablon prompt)\n"
            "  Bilimlar bazasi (boshlang'ich)\n"
            "  Menyu tugmalari (shablon)\n"
            "  Lead pipeline (tayyor)\n\n"
            "Tez amallar:"
        )

        await callback.message.answer(
            summary,
            reply_markup=_setup_complete_keyboard(),
        )

    except Exception:
        log.exception("auto_onboarding_failed", user_id=user_id)
        await state.clear()
        await callback.message.answer(
            "Xatolik yuz berdi. Qaytadan urinib ko'ring: /start",
            reply_markup=main_menu_keyboard(),
        )


@router.callback_query(
    StateFilter(AutoOnboardingStates.confirmation),
    F.data == "aonb:cancel",
)
async def handle_cancel(
    callback: CallbackQuery, state: FSMContext, **data,
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.clear()
    await callback.message.answer(
        "Biznes yaratish bekor qilindi.\n"
        "Qaytadan boshlash: /start",
    )


# ── Quick action callbacks ───────────────────────────────────────────────────


@router.callback_query(F.data == "aonb:go:leads")
async def cb_go_leads(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.answer(
        "CRM dashboard uchun /my_leads buyrug'ini yuboring.",
    )


@router.callback_query(F.data == "aonb:go:knowledge")
async def cb_go_knowledge(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.answer(
        "Bilimlar bazasini boshqarish: /knowledge",
    )


@router.callback_query(F.data == "aonb:go:ai")
async def cb_go_ai(callback: CallbackQuery, state: FSMContext, **data) -> None:
    await callback.answer()
    await callback.message.answer(
        "AI yordamchini sinash uchun istalgan savolingizni yozing.\n"
        "Masalan: \"Narxlar qanday?\"",
    )


@router.callback_query(F.data == "aonb:go:bot_status")
async def cb_go_bot_status(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.answer(
        "Bot holatini ko'rish: /bot_status",
    )


@router.callback_query(F.data == "aonb:go:subscription")
async def cb_go_subscription(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.answer(
        "Obuna ma'lumotlari: /subscription",
    )


# ── Default knowledge seeding ────────────────────────────────────────────────


async def _seed_default_knowledge(
    tenant_id: int,
    btype: BusinessType,
    business_name: str,
) -> None:
    """Create starter knowledge base entries for a new tenant."""
    from infrastructure.database.models.ai_knowledge import TenantAiKnowledgeModel
    from infrastructure.database.session import get_session_factory

    entries = _get_default_entries(btype, business_name)
    if not entries:
        return

    factory = get_session_factory()
    try:
        async with factory() as session:
            for entry in entries:
                model = TenantAiKnowledgeModel(
                    tenant_id=tenant_id,
                    category=entry["category"],
                    title=entry["title"],
                    content=entry["content"],
                )
                session.add(model)
            await session.commit()

        log.info(
            "auto_onboarding_knowledge_seeded",
            tenant_id=tenant_id,
            count=len(entries),
        )
    except Exception:
        log.warning(
            "auto_onboarding_knowledge_seed_failed",
            tenant_id=tenant_id,
        )


def _get_default_entries(
    btype: BusinessType, business_name: str,
) -> list[dict]:
    """Return starter knowledge entries by business type."""
    common = [
        {
            "category": "faq",
            "title": "Ish vaqti",
            "content": f"{business_name} dushanba-shanba, 09:00 dan 18:00 gacha ishlaydi.",
        },
        {
            "category": "faq",
            "title": "Bog'lanish",
            "content": f"{business_name} bilan bog'lanish uchun operator tugmasini bosing.",
        },
    ]

    type_entries: dict[BusinessType, list[dict]] = {
        BusinessType.CEILING: [
            {
                "category": "service",
                "title": "Xizmatlar",
                "content": (
                    f"{business_name} quyidagi xizmatlarni taqdim etadi:\n"
                    "- Matviy potolok o'rnatish\n"
                    "- Yaltiroq potolok o'rnatish\n"
                    "- Ko'p darajali potolok\n"
                    "- LED podsvetka\n"
                    "- Bepul o'lchov xizmati"
                ),
            },
            {
                "category": "pricing",
                "title": "Narxlar diapazoni",
                "content": (
                    "Narxlar dizayn turiga qarab farqlanadi:\n"
                    "- Matviy oq: 120,000 so'm/m² dan\n"
                    "- Yaltiroq: 130,000 so'm/m² dan\n"
                    "- Premium dizaynlar: 180,000-300,000 so'm/m²\n"
                    "Aniq narx o'lchov natijasiga bog'liq."
                ),
            },
        ],
        BusinessType.RESTAURANT: [
            {
                "category": "service",
                "title": "Xizmatlar",
                "content": (
                    f"{business_name} xizmatlari:\n"
                    "- Zalda ovqatlanish\n"
                    "- Yetkazib berish\n"
                    "- Olib ketish\n"
                    "- Tadbirlar uchun buyurtma"
                ),
            },
        ],
        BusinessType.AUTO_SERVICE: [
            {
                "category": "service",
                "title": "Xizmatlar",
                "content": (
                    f"{business_name} xizmatlari:\n"
                    "- Diagnostika\n"
                    "- Moy almashtirish\n"
                    "- Tormoz tizimi\n"
                    "- Dvigatel ta'miri\n"
                    "- Shassi ta'miri"
                ),
            },
        ],
        BusinessType.CLINIC: [
            {
                "category": "service",
                "title": "Xizmatlar",
                "content": (
                    f"{business_name} xizmatlari:\n"
                    "- Umumiy tekshiruv\n"
                    "- Laboratoriya tahlillari\n"
                    "- Mutaxassis qabuli\n"
                    "- Online maslahat"
                ),
            },
        ],
    }

    specific = type_entries.get(btype, [])
    return common + specific
