"""
AI-powered free-text handler for private DM chats.

Pipeline
--------
  Incoming text (no active FSM state)
    |- Dimension pair found (e.g. "5x4", "5m 4m") -> jump to pricing FSM at design step
    |- Single bare number (e.g. "5")               -> start pricing FSM at width step
    +- General question                            -> OpenAI JSON reply + intent keyboard

This file contains ONLY router handlers and wiring.  All business logic
has been extracted into sibling modules:

  ai_states.py           - FSM states, keyboards, text constants
  ai_detection.py        - Intent / trigger detection, text parsing
  ai_memory.py           - Redis AI memory + stats
  ai_scoring.py          - Lead scoring + objection detection / handling
  ai_openai.py           - OpenAI integration + conversation DB helpers
  ai_notifications.py    - Admin notification orchestration
  ai_followups.py        - Async delayed follow-up tasks
  ai_pricing_helpers.py  - Price display helpers
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.main_menu import BTN_AI, main_menu_keyboard
from apps.bot.ai.system_prompt import _parse_ai_scoring, build_system_prompt
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_tenant_ai_config
from shared.config import get_settings
from shared.logging import get_logger
from shared.utils.phone import extract_phone_from_text

# ── Sibling module imports ──────────────────────────────────────────────────
from apps.bot.handlers.private.ai_states import (  # noqa: F401
    AiSupportStates,
    _EXIT_TEXTS,
    _CANCEL_PHONE,
    _FAILSAFE_TEXT,
    _FAILSAFE_KB,
    _NEUTRAL_REPLY,
    _CATALOG_SOFT_CTA,
    _CATALOG_INTRO,
    _PRICE_ASK_DESIGN_TEXT,
    _ai_keyboard,
    _phone_request_keyboard,
)
from apps.bot.handlers.private.ai_detection import (  # noqa: F401
    _is_measurement_request,
    _is_catalog_request,
    _detect_catalog_context,
    _build_smart_catalog_response,
    _catalog_link_kb,
    _is_price_query,
    parse_combo,
    _normalize_room,
    _GENERIC_CONFIRMATIONS,
    _is_greeting,
    _detect_room_type,
    _room_design_text,
    is_valid_name,
    normalize_name,
    _parse_area,
    detect_district,
)
from apps.bot.handlers.private.ai_memory import (  # noqa: F401
    _load_ai_memory,
    _save_ai_memory,
    _build_greeting_from_memory,
    _update_ai_memory_from_interaction,
    _ai_stats_incr,
    _ai_stats_count_user,
)
from apps.bot.handlers.private.ai_scoring import (  # noqa: F401
    _get_lead_score,
    _add_lead_score,
    classify_score,
    detect_objection,
    _handle_objection,
)
from apps.bot.handlers.private.ai_openai import (
    _build_context_block,
    _load_context,
    _persist_exchange,
    clear_ai_conversation,  # noqa: F401 — re-exported for support.py
    _store_user_message_only,
    _call_ai,
)
from apps.bot.handlers.private.ai_notifications import (
    _update_lead_ai_scoring,
    _notify_phone_captured,
    _notify_ai_lead_collected,
    _notify_warm_interest,
)
from apps.bot.handlers.private.ai_followups import (
    _schedule_catalog_followup,
    _schedule_ai_followup,
    _refresh_ai_followup_nonce,
    _photo_followup_task,
    _enter_photo_funnel,
)
from apps.bot.handlers.private.ai_pricing_helpers import (
    _show_price_upsell,
    _show_combo_confirmation,
)

log = get_logger(__name__)
router = Router(name="private:ai_support")


# ── Explicit AI mode — entry ────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == BTN_AI)
async def cmd_ai_start(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Enter dedicated AI chat mode (private only; redirect groups to DM)."""
    if message.from_user is None:
        return
    if message.chat.type != "private":
        settings = get_settings()
        bot_username = settings.bot.username or "bot"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="💬 Madina bilan suhbat",
                url=f"https://t.me/{bot_username}?start=ai",
            )
        ]])
        await message.answer(
            "🤖 AI yordamchisi faqat shaxsiy chatda ishlaydi. "
            "Quyidagi tugma orqali bot bilan to'g'ridan-to'g'ri yozing:",
            reply_markup=kb,
        )
        return
    user_id = message.from_user.id
    _bot_id = message.bot.id if message.bot else None
    _mem = await _load_ai_memory(user_id, bot_id=_bot_id)

    await state.clear()

    if _mem.get("name"):
        await state.set_state(AiSupportStates.waiting_for_ai_question)
        await state.update_data(user_name=_mem["name"])
        await message.answer(_build_greeting_from_memory(_mem), reply_markup=_ai_keyboard())
        return

    await state.set_state(AiSupportStates.waiting_for_name)
    await message.answer(
        "Salom! 👋\n\n"
        "Men Madina — VashPotolok kompaniyasining AI mutaxassisiman. 🤖\n"
        "Sizga natijnoy potolok bo'yicha maslahat beraman.\n\n"
        "Masalan men sizga yordam bera olaman:\n\n"
        "💰 Potolok narxini hisoblash\n"
        "🎨 Dizayn variantlarini tanlash\n"
        "📐 Xona uchun eng yaxshi potolok turini tavsiya qilish\n"
        "🧾 Zakaz qoldirish yoki operator bilan bog'lash\n\n"
        "Avval tanishib olaylik 🙂\n\n"
        "Ismingiz nima?",
        reply_markup=_ai_keyboard(),
    )


# ── Name collection ─────────────────────────────────────────────────────────

_NAME_REJECT_KEYWORDS: frozenset[str] = frozenset({
    "zakaz", "buyurtma", "narx", "qancha", "nech", "pul",
    "katalog", "rasm", "dizayn", "variant", "operator",
    "telefon", "aloqa", "tuman", "m2", "kv", "kvadrat",
})


@router.message(
    StateFilter(AiSupportStates.waiting_for_name),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_name_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Collect user's name; if input is not a name, handle intent instead."""
    text = (message.text or "").strip()

    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return

    if is_valid_name(text):
        name = normalize_name(text)
        await state.set_state(AiSupportStates.waiting_for_ai_question)
        await state.update_data(user_name=name)
        if message.from_user:
            asyncio.create_task(
                _update_ai_memory_from_interaction(
                    message.from_user.id, text=text, fsm_data={"user_name": name},
                    bot_id=message.bot.id if message.bot else None,
                )
            )
        await message.answer(
            f"Juda yaxshi, {name} 🙂\n\n"
            "Sizga tezroq yordam berishim uchun kichkina savol:\n\n"
            "Potolok qaysi xona uchun kerak?\n\n"
            "🏠 Mehmonxona\n"
            "🛏 Yotoqxona\n"
            "🍳 Oshxona\n"
            "🚿 Hammom\n\n"
            "Va taxminan xona **necha m²**?",
            reply_markup=_ai_keyboard(),
        )
        return

    await state.set_state(AiSupportStates.waiting_for_ai_question)

    if _is_measurement_request(text):
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    await handle_ai_question(message, state, **data)

    if await state.get_state() == AiSupportStates.waiting_for_ai_question.state:
        await message.answer(
            "Aytgancha, ismingizni ham yozib yuboring 🙂",
            reply_markup=_ai_keyboard(),
        )


# ── District collection ─────────────────────────────────────────────────────

@router.message(
    StateFilter(AiSupportStates.waiting_for_district),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_district_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Collect district, then ask for phone number."""
    text = (message.text or "").strip()
    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return
    await state.update_data(price_district=text)
    await state.set_state(AiSupportStates.waiting_for_phone)
    kb = _phone_request_keyboard() if message.chat.type == "private" else _ai_keyboard()
    await message.answer(
        "Zakazni rasmiylashtirish uchun telefon raqamingizni yuboring 🙂",
        reply_markup=kb,
    )


# ── Phone collection (contact share) ────────────────────────────────────────

@router.message(
    StateFilter(AiSupportStates.waiting_for_phone),
    F.contact,
)
async def handle_phone_contact(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Handle Telegram contact share."""
    contact = message.contact
    if contact is None or not contact.phone_number:
        await message.answer(
            "Telefon raqamni shunday yozing:\n90xxxxxxx yoki +99890xxxxxxx",
            reply_markup=_phone_request_keyboard(),
        )
        return

    raw = contact.phone_number
    _digits = re.sub(r"\D", "", raw)
    if len(_digits) == 12 and _digits.startswith("998"):
        phone = f"+{_digits}"
    elif len(_digits) == 9:
        phone = f"+998{_digits}"
    elif len(_digits) == 10 and _digits.startswith("0"):
        phone = f"+998{_digits[1:]}"
    else:
        phone = None

    if phone is None:
        await message.answer(
            "Telefon raqamni shunday yozing:\n90xxxxxxx yoki +99890xxxxxxx",
            reply_markup=_phone_request_keyboard(),
        )
        return

    await _complete_phone_step(message, state, phone)


# ── Phone step completion (shared by contact and text input) ─────────────────

async def _complete_phone_step(message: Message, state: FSMContext, phone: str) -> None:
    """Shared success path for both contact-share and manual phone entry."""
    fsm_data = await state.get_data()
    _phone_user_id = message.from_user.id if message.from_user else 0
    _bot_id = message.bot.id if message.bot else None
    _lead_score = 0
    if _phone_user_id:
        _lead_score = await _add_lead_score(_phone_user_id, 40, bot_id=_bot_id)
    await state.update_data(price_phone=phone)
    await state.set_state(AiSupportStates.waiting_for_ai_question)
    await message.answer(
        "Rahmat 🙂\n"
        "Ma'lumotlaringiz qabul qilindi.\n"
        "Mutaxassisimiz tez orada siz bilan bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Boshqa savollaringiz bormi?", reply_markup=_ai_keyboard())
    asyncio.create_task(_ai_stats_incr("phones_received", bot_id=_bot_id))
    asyncio.create_task(_ai_stats_incr(f"lead_{classify_score(_lead_score)}", bot_id=_bot_id))
    if _phone_user_id:
        _fsm_snap = dict(fsm_data)

        async def _mark_phone_captured(uid: int = _phone_user_id, snap: dict = _fsm_snap, _bid: int | None = _bot_id) -> None:
            mem = await _load_ai_memory(uid, bot_id=_bid)
            mem["phone_captured"] = True
            if not mem.get("district") and snap.get("price_district"):
                mem["district"] = snap["price_district"]
            if not mem.get("area_m2") and snap.get("price_area"):
                mem["area_m2"] = snap["price_area"]
            await _save_ai_memory(uid, mem, bot_id=_bid)
            try:
                from infrastructure.cache.client import get_redis
                from infrastructure.cache.keys import CacheKeys, CacheTTL
                redis = get_redis()
                fu_state = (await redis.get_json(CacheKeys.ai_followup_state(uid, bot_id=_bid))) or {}
                fu_state["lead_created"] = True
                await redis.set_json(
                    CacheKeys.ai_followup_state(uid, bot_id=_bid),
                    fu_state,
                    ttl=CacheTTL.AI_FOLLOWUP_STATE,
                )
            except Exception:
                pass

        asyncio.create_task(_mark_phone_captured())

    _ai_mem = await _load_ai_memory(_phone_user_id, bot_id=_bot_id) if _phone_user_id else {}
    _resolved_lead_id: int | None = None
    if _phone_user_id:
        try:
            factory = get_session_factory()
            async with factory() as _ld_sess:
                from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
                _ld_list = await PostgresLeadRepository(_ld_sess).list_by_user(_phone_user_id, limit=1)
                if _ld_list:
                    _resolved_lead_id = _ld_list[0].id
        except Exception:
            pass
    asyncio.create_task(
        _notify_ai_lead_collected(
            phone=phone,
            district=fsm_data.get("price_district") or "",
            area=fsm_data.get("price_area"),
            room=fsm_data.get("price_room"),
            design=fsm_data.get("price_design"),
            name=fsm_data.get("price_name") or fsm_data.get("user_name"),
            from_user=message.from_user,
            score=_lead_score,
            last_message=fsm_data.get("last_user_message") or "",
            lead_id=_resolved_lead_id,
            last_objection=_ai_mem.get("last_objection"),
            closing_attempted=bool(_ai_mem.get("last_closing_attempt")),
            closing_action=_ai_mem.get("last_closing_attempt"),
            intent=_ai_mem.get("last_intent"),
            closing_confidence=None,
            negotiation_tactic=_ai_mem.get("last_negotiation_tactic"),
            negotiation_escalated=bool(_ai_mem.get("negotiation_escalated")),
            last_activity_ts=_ai_mem.get("updated_at"),
            memory_created_at=_ai_mem.get("created_at"),
        )
    )


# ── Phone collection (text input) ───────────────────────────────────────────

@router.message(
    StateFilter(AiSupportStates.waiting_for_phone),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_phone_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Collect phone (manual text entry), confirm, and fire admin notification."""
    text = (message.text or "").strip()
    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return
    if text == _CANCEL_PHONE:
        await state.set_state(AiSupportStates.waiting_for_ai_question)
        await message.answer(
            "Mayli, keyinroq ham bo'ladi 🙂 Boshqa savollaringiz bormi?",
            reply_markup=_ai_keyboard(),
        )
        return
    _digits = re.sub(r"\D", "", text)
    if len(_digits) == 12 and _digits.startswith("998"):
        phone = f"+{_digits}"
    elif len(_digits) == 9:
        phone = f"+998{_digits}"
    elif len(_digits) == 10 and _digits.startswith("0"):
        phone = f"+998{_digits[1:]}"
    else:
        phone = None
    if phone is None:
        await message.answer(
            "Telefon raqamni shunday yozing:\n90xxxxxxx yoki +99890xxxxxxx",
            reply_markup=_phone_request_keyboard() if message.chat.type == "private" else _ai_keyboard(),
        )
        return
    await _complete_phone_step(message, state, phone)


# ── AI exit handlers ────────────────────────────────────────────────────────

@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text.in_(_EXIT_TEXTS),
)
async def handle_ai_exit(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Exit AI mode and return to main menu."""
    await state.clear()
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())


@router.message(StateFilter(AiSupportStates.waiting_for_ai_question), Command("ai_off"))
async def handle_ai_off(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Exit AI mode via /ai_off command."""
    await state.clear()
    await message.answer("🤖 AI rejim o'chirildi.", reply_markup=main_menu_keyboard())


# ── Photo funnel handlers ───────────────────────────────────────────────────

@router.message(
    StateFilter(AiSupportStates.waiting_photo),
    F.photo,
    F.chat.type == "private",
)
async def handle_photo_received(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Photo received -> ask room type."""
    await state.set_state(AiSupportStates.waiting_room)
    await message.answer(
        "📸 Rasm qabul qilindi ✅\n\n"
        "Bu qanday xona? (masalan: mehmonxona/zal/terassa, oshxona, dush/hammom, spalniy)",
        reply_markup=_ai_keyboard(),
    )


@router.message(
    StateFilter(AiSupportStates.waiting_photo),
    F.text,
    ~F.text.startswith("/"),
    F.chat.type == "private",
)
async def handle_photo_state_text(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Non-photo message while waiting for photo -> re-prompt."""
    text = (message.text or "").strip()
    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return
    await message.answer(
        "📸 Iltimos, xonangizni rasmini yuboring.",
        reply_markup=_ai_keyboard(),
    )


@router.message(
    StateFilter(AiSupportStates.waiting_room),
    F.text,
    ~F.text.startswith("/"),
    F.chat.type == "private",
)
async def handle_room_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Detect room type -> send recommendations + catalog button + ask area."""
    text = (message.text or "").strip()
    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return

    room = _detect_room_type(text)
    await state.update_data(price_room=room)

    await message.answer(_room_design_text(room), reply_markup=_catalog_link_kb())
    await message.answer(
        "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
        reply_markup=_ai_keyboard(),
    )

    await state.set_state(AiSupportStates.waiting_area_photo)

    fsm_data = await state.get_data()
    if not fsm_data.get("photo_followup_scheduled") and message.bot and message.from_user:
        await state.update_data(photo_followup_scheduled=True)
        asyncio.create_task(
            _photo_followup_task(
                bot=message.bot,
                chat_id=message.chat.id,
                storage=state.storage,
                state_key=state.key,
            )
        )


@router.message(
    StateFilter(AiSupportStates.waiting_area_photo),
    F.text,
    ~F.text.startswith("/"),
    F.chat.type == "private",
)
async def handle_area_photo_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Collect area in photo funnel -> ask district immediately."""
    text = (message.text or "").strip()
    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return

    area = _parse_area(text)
    if area is not None:
        await state.update_data(price_area=area)
        await state.set_state(AiSupportStates.waiting_for_district)
        await message.answer(
            f"✅ {area:g} m² qabul qilindi.\n\n"
            "Usta kelib bepul o'lchov qilib beradi! 🙂\n\n"
            "Qaysi tumandasiz?",
            reply_markup=_ai_keyboard(),
        )
    else:
        await message.answer(
            "Masalan: 20 m² yoki 5x3 formatda yozing.",
            reply_markup=_ai_keyboard(),
        )


# ── Sales escalation helper ────────────────────────────────────────────────


async def _log_suspicious_prompt(
    *,
    user_id: int,
    text: str,
    risk_level: str,
    matched_patterns: tuple[str, ...],
    tenant_id: int | None,
    db_session: Any | None,
) -> None:
    """Log a suspicious prompt injection attempt to audit_logs. Never raises."""
    try:
        if db_session is not None:
            from infrastructure.database.repositories.audit_log_repo import (
                PostgresAuditLogRepository,
            )
            repo = PostgresAuditLogRepository(db_session, tenant_id)
            await repo.insert(
                actor_id=user_id if user_id > 0 else None,
                action="prompt_injection_attempt",
                entity_type="ai_prompt",
                entity_id=user_id,
                new_value={
                    "message": text[:500],
                    "risk_level": risk_level,
                    "matched_patterns": list(matched_patterns),
                },
            )
        else:
            log.warning(
                "prompt_injection_no_session",
                user_id=user_id,
                risk_level=risk_level,
                patterns=matched_patterns,
            )
    except Exception:
        log.exception("prompt_injection_audit_failed", user_id=user_id)


async def _log_rate_limit_violation(
    *,
    user_id: int,
    reason: str,
    tenant_id: int | None,
    db_session: Any | None,
) -> None:
    """Log a rate limit violation to audit_logs. Never raises."""
    try:
        if db_session is not None:
            from infrastructure.database.repositories.audit_log_repo import (
                PostgresAuditLogRepository,
            )
            repo = PostgresAuditLogRepository(db_session, tenant_id)
            await repo.insert(
                actor_id=user_id if user_id > 0 else None,
                action="rate_limit_exceeded",
                entity_type="rate_limit",
                entity_id=user_id,
                new_value={
                    "reason": reason,
                    "tenant_id": tenant_id,
                },
            )
        else:
            log.warning(
                "rate_limit_no_session",
                user_id=user_id,
                reason=reason,
            )
    except Exception:
        log.exception("rate_limit_audit_failed", user_id=user_id)


async def _maybe_escalate(
    message: Message,
    user_id: int,
    *,
    intent: str,
    score: int,
    lead_temperature: str | None,
    closing_confidence: float | None,
    last_message: str,
    data: dict[str, Any],
) -> None:
    """Fire-and-forget: escalate HOT lead to tenant admin group. Never raises."""
    try:
        from core.services.sales_escalation_service import (
            check_escalation_cooldown,
            send_escalation,
            should_escalate,
        )

        _esc_bot_id = message.bot.id if message.bot else None
        memory = await _load_ai_memory(user_id, bot_id=_esc_bot_id)
        decision = should_escalate(
            score=score,
            intent=intent,
            lead_temperature=lead_temperature,
            closing_confidence=closing_confidence,
            phone_captured=bool(memory.get("phone_captured")),
            has_area=memory.get("area_m2") is not None,
        )
        if not decision.should:
            return

        # Resolve admin group — tenant-aware
        tenant_config = data.get("tenant_config")
        admin_group_id = (
            getattr(tenant_config, "admin_group_id", None)
            if tenant_config
            else None
        ) or get_settings().bot.admin_group_id
        if not admin_group_id or not message.bot:
            return

        bot_id = message.bot.id
        if not await check_escalation_cooldown(user_id, bot_id=bot_id):
            log.debug("escalation_cooldown", user_id=user_id)
            return

        await send_escalation(
            bot=message.bot,
            admin_group_id=admin_group_id,
            user_id=user_id,
            score=score,
            intent=intent,
            lead_temperature=lead_temperature,
            closing_confidence=closing_confidence,
            name=memory.get("name"),
            username=message.from_user.username if message.from_user else None,
            last_message=last_message,
            reason=decision.reason,
        )
    except Exception:
        log.warning("escalation_failed", user_id=user_id)


# ── Explicit AI question handler ────────────────────────────────────────────

@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_(_EXIT_TEXTS),
)
async def handle_ai_question(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Answer questions with the AI service while in explicit AI mode."""
    text = _normalize_room(message.text or "")
    user_id = message.from_user.id if message.from_user else 0
    _bot_id = message.bot.id if message.bot else None

    asyncio.create_task(_ai_stats_incr("messages_total", bot_id=_bot_id))
    if user_id:
        asyncio.create_task(_ai_stats_count_user(user_id, bot_id=_bot_id))

    if user_id and _is_greeting(text):
        _mem = await _load_ai_memory(user_id, bot_id=_bot_id)
        if _mem.get("name"):
            await message.answer(_build_greeting_from_memory(_mem), reply_markup=_ai_keyboard())
            return

    if message.bot and user_id and message.chat.type == "private":
        _nonce = await _refresh_ai_followup_nonce(user_id, bot_id=_bot_id)
        _schedule_ai_followup(
            bot=message.bot, chat_id=message.chat.id, user_id=user_id,
            nonce=_nonce, storage=state.storage, state_key=state.key,
        )

    await state.update_data(last_user_message=text[:200])

    if _is_measurement_request(text):
        asyncio.create_task(_ai_stats_incr("orders_started", bot_id=_bot_id))
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 25, bot_id=_bot_id))
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    if _is_catalog_request(text):
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 5, bot_id=_bot_id))
        room, design = _detect_catalog_context(text)
        await message.answer(
            _build_smart_catalog_response(room, design),
            reply_markup=_catalog_link_kb(),
        )
        await message.answer(_CATALOG_SOFT_CTA, reply_markup=_ai_keyboard())
        fsm_data = await state.get_data()
        asyncio.create_task(
            _notify_warm_interest(
                topic=room or design or "katalog / dizayn",
                from_user=message.from_user,
                name=fsm_data.get("user_name"),
            )
        )
        if message.bot and message.from_user:
            _schedule_catalog_followup(
                bot=message.bot,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                storage=state.storage,
                state_key=state.key,
            )
        return

    _norm = (message.text or "").lower().strip()
    if _norm in _GENERIC_CONFIRMATIONS:
        await message.answer(_NEUTRAL_REPLY)
        return

    _obj = detect_objection(text)
    if _obj:
        await _handle_objection(_obj, message, state, user_id)
        return

    _combo = parse_combo(text)
    _price_area = _combo["area"]
    if _is_price_query(text) or _price_area is not None:
        if _price_area is not None:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 15 + (10 if _combo["district"] else 0), bot_id=_bot_id))
            await _show_price_upsell(
                message, state, _price_area,
                district=_combo["district"], design=_combo["design"],
            )
        elif _combo["district"]:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10, bot_id=_bot_id))
            await state.update_data(price_district=_combo["district"])
            await message.answer(
                f"📍 Tuman: {_combo['district']}\n\n"
                "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                reply_markup=_ai_keyboard(),
            )
        else:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10, bot_id=_bot_id))
            if _combo["design"]:
                await message.answer(
                    "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                    reply_markup=_ai_keyboard(),
                )
            else:
                await message.answer(_PRICE_ASK_DESIGN_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Rate limiting (unified) ──────────────────────────────────────────
    db_user = data.get("db_user")
    from core.security.rate_limiter import check_rate_limits
    from shared.constants.enums import UserRole

    _is_admin = (
        db_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN)
        if db_user and hasattr(db_user, "role")
        else False
    )
    rl_result = await check_rate_limits(
        user_id=user_id,
        tenant_id=db_user.tenant_id if db_user else None,
        is_ai_request=True,
        is_admin=_is_admin,
    )
    if not rl_result.allowed:
        asyncio.create_task(_log_rate_limit_violation(
            user_id=user_id,
            reason=rl_result.reason.value if rl_result.reason else "unknown",
            tenant_id=db_user.tenant_id if db_user else None,
            db_session=data.get("db_session"),
        ))
        await message.answer(
            f"⏳ {rl_result.denial_message}",
            reply_markup=_ai_keyboard(),
        )
        return

    # ── Plan-based AI daily limit ─────────────────────────────────────
    _tenant_id = db_user.tenant_id if db_user else None
    if _tenant_id is not None:
        try:
            from core.services.usage_service import check_ai_limit

            _plan = data.get("tenant_plan")  # set by middleware if available
            _ai_check = await check_ai_limit(_tenant_id, _plan)
            if not _ai_check.allowed:
                await message.answer(
                    f"⚠️ {_ai_check.reason}",
                    reply_markup=_ai_keyboard(),
                )
                return
        except Exception:
            pass  # fail open

    # ── Prompt injection detection ────────────────────────────────────
    from core.security.prompt_sanitizer import scan_prompt

    scan = scan_prompt(text)
    if scan.risk_level.value != "none":
        asyncio.create_task(_log_suspicious_prompt(
            user_id=user_id,
            text=text,
            risk_level=scan.risk_level.value,
            matched_patterns=scan.matched_patterns,
            tenant_id=db_user.tenant_id if db_user else None,
            db_session=data.get("db_session"),
        ))
    if scan.blocked:
        log.warning(
            "prompt_injection_blocked",
            user_id=user_id,
            patterns=scan.matched_patterns,
        )
        await message.answer(
            "Kechirasiz, bu turdagi so'rovga javob bera olmayman.\n"
            "Stretch potoloklar haqida savol bering! 😊",
            reply_markup=_ai_keyboard(),
        )
        return
    text = scan.sanitized_text

    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # ── Resolve tenant-specific system prompt ─────────────────────────────
    db_session = data.get("db_session")
    tenant_prompt, tenant_kb = (
        await get_tenant_ai_config(db_session, db_user.tenant_id)
        if db_user and db_session
        else (None, None)
    )
    system_prompt = build_system_prompt(tenant_prompt, tenant_kb)

    # ── Append tenant knowledge base entries ───────────────────────────
    from core.services.ai_knowledge_service import get_tenant_knowledge_block

    _tenant_id = db_user.tenant_id if db_user else None
    kb_block = await get_tenant_knowledge_block(_tenant_id, text)
    if kb_block:
        system_prompt = system_prompt + kb_block

    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)
    _has_history = bool(history)

    # ── AI response cache ─────────────────────────────────────────────
    from core.services.ai_cache_service import get_cached_response, store_response

    _cache_hit = False
    cached = await get_cached_response(_tenant_id, text, has_history=_has_history)
    if cached is not None:
        result = cached
        _cache_hit = True
        asyncio.create_task(_ai_stats_incr("cache_hit", bot_id=_bot_id))
    else:
        asyncio.create_task(_ai_stats_incr("cache_miss", bot_id=_bot_id))

    if not _cache_hit:
        try:
            result = await _call_ai(text, history, context_block, system_prompt=system_prompt)
        except Exception:
            log.exception("ai_call_failed", user_id=user_id)
            await _store_user_message_only(
                user_id=user_id, user_text=text, current_messages=history
            )
            await message.answer(_FAILSAFE_TEXT, reply_markup=_ai_keyboard())
            return

    try:
        intent = str(result.get("intent", "other"))
        reply_text = str(result.get("reply", "")).strip()
        extracted: dict[str, Any] = result.get("extracted") or {}
        lead_temperature, closing_confidence = _parse_ai_scoring(result)
        if not reply_text:
            raise ValueError("empty AI reply")
    except Exception:
        log.exception("ai_call_failed", user_id=user_id)
        await _store_user_message_only(
            user_id=user_id, user_text=text, current_messages=history
        )
        await message.answer(_FAILSAFE_TEXT, reply_markup=_ai_keyboard())
        return

    if not _cache_hit:
        asyncio.create_task(store_response(
            _tenant_id, text, result, has_history=_has_history,
        ))

    await message.answer(reply_text, reply_markup=_ai_keyboard())

    _closer_score = await _get_lead_score(user_id, bot_id=_bot_id)

    try:
        from apps.bot.handlers.private.sales_closer import attempt_close
        await attempt_close(
            message, state, user_id,
            intent=intent,
            score=_closer_score,
            closing_confidence=closing_confidence,
        )
    except Exception:
        pass

    # Escalate HOT leads to tenant admin group (fire-and-forget)
    asyncio.create_task(_maybe_escalate(
        message, user_id,
        intent=intent, score=_closer_score,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
        last_message=text[:200],
        data=data,
    ))

    await _persist_exchange(
        user_id=user_id,
        user_text=text,
        assistant_text=reply_text,
        intent=intent,
        extracted=extracted,
        current_profile=profile,
        current_messages=history,
        current_summary=summary,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
    )
    if lead_temperature is not None or closing_confidence is not None:
        asyncio.create_task(
            _update_lead_ai_scoring(
                user_id=user_id,
                lead_temperature=lead_temperature,
                closing_confidence=closing_confidence,
            )
        )
    _fsm_for_mem = await state.get_data()
    asyncio.create_task(
        _update_ai_memory_from_interaction(
            user_id, text=text, fsm_data=_fsm_for_mem,
            first_name=message.from_user.first_name if message.from_user else None,
            bot_id=_bot_id,
        )
    )
    log.info(
        "ai_reply_sent",
        user_id=user_id,
        intent=intent,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
        mode="explicit",
    )


# ── Passive handler (default_state catch-all) ───────────────────────────────

@router.message(
    F.chat.type == "private",
    F.text,
    ~F.text.startswith("/"),
    StateFilter(default_state),
)
async def handle_ai_message(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Route free-text DMs: dimension shortcut or AI reply with persistent memory."""
    text = message.text or ""
    user_id = message.from_user.id if message.from_user else 0
    _bot_id = message.bot.id if message.bot else None

    asyncio.create_task(_ai_stats_incr("messages_total", bot_id=_bot_id))
    if user_id:
        asyncio.create_task(_ai_stats_count_user(user_id, bot_id=_bot_id))

    if user_id and _is_greeting(text):
        _mem = await _load_ai_memory(user_id, bot_id=_bot_id)
        if _mem.get("name"):
            await message.answer(_build_greeting_from_memory(_mem), reply_markup=_ai_keyboard())
            return

    detected_phone = extract_phone_from_text(text)
    if detected_phone:
        try:
            factory = get_session_factory()
            async with factory() as session:
                mem = await session.get(AiMemoryModel, user_id)
                _profile_for_phone: dict[str, Any] = mem.profile if mem else {}
        except Exception:
            _profile_for_phone = {}

        if not _profile_for_phone.get("phone"):
            asyncio.create_task(
                _notify_phone_captured(
                    phone=detected_phone,
                    profile=_profile_for_phone,
                    from_user=message.from_user,
                    chat_type=message.chat.type,
                    chat_id=message.chat.id,
                )
            )

    if message.bot and user_id and message.chat.type == "private":
        _nonce = await _refresh_ai_followup_nonce(user_id, bot_id=_bot_id)
        _schedule_ai_followup(
            bot=message.bot, chat_id=message.chat.id, user_id=user_id,
            nonce=_nonce, storage=state.storage, state_key=state.key,
        )

    if _is_measurement_request(text):
        asyncio.create_task(_ai_stats_incr("orders_started", bot_id=_bot_id))
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 25, bot_id=_bot_id))
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    if _is_catalog_request(text):
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 5, bot_id=_bot_id))
        room, design = _detect_catalog_context(text)
        await message.answer(
            _build_smart_catalog_response(room, design),
            reply_markup=_catalog_link_kb(),
        )
        await message.answer(_CATALOG_SOFT_CTA, reply_markup=_ai_keyboard())
        asyncio.create_task(
            _notify_warm_interest(
                topic=room or design or "katalog / dizayn",
                from_user=message.from_user,
            )
        )
        if message.bot and message.from_user:
            _schedule_catalog_followup(
                bot=message.bot,
                chat_id=message.chat.id,
                user_id=message.from_user.id,
                storage=state.storage,
                state_key=state.key,
            )
        return

    _norm = (message.text or "").lower().strip()
    if _norm in _GENERIC_CONFIRMATIONS:
        await message.answer(_NEUTRAL_REPLY)
        return

    _obj = detect_objection(text)
    if _obj:
        await _handle_objection(_obj, message, state, user_id)
        return

    _combo = parse_combo(text)
    area = _combo["area"]
    if _is_price_query(text) or area is not None:
        if area is not None:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 15 + (10 if _combo["district"] else 0), bot_id=_bot_id))
            await _show_price_upsell(
                message, state, area,
                district=_combo["district"], design=_combo["design"],
            )
        elif _combo["district"]:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10, bot_id=_bot_id))
            await state.update_data(price_district=_combo["district"])
            await message.answer(
                f"📍 Tuman: {_combo['district']}\n\n"
                "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                reply_markup=_ai_keyboard(),
            )
        else:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10, bot_id=_bot_id))
            if _combo["design"]:
                await message.answer(
                    "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                    reply_markup=_ai_keyboard(),
                )
            else:
                await message.answer(_PRICE_ASK_DESIGN_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Rate limiting (unified) ──────────────────────────────────────────
    db_user = data.get("db_user")
    from core.security.rate_limiter import check_rate_limits
    from shared.constants.enums import UserRole

    _is_admin = (
        db_user.role in (UserRole.ADMIN, UserRole.SUPERADMIN)
        if db_user and hasattr(db_user, "role")
        else False
    )
    rl_result = await check_rate_limits(
        user_id=user_id,
        tenant_id=db_user.tenant_id if db_user else None,
        is_ai_request=True,
        is_admin=_is_admin,
    )
    if not rl_result.allowed:
        asyncio.create_task(_log_rate_limit_violation(
            user_id=user_id,
            reason=rl_result.reason.value if rl_result.reason else "unknown",
            tenant_id=db_user.tenant_id if db_user else None,
            db_session=data.get("db_session"),
        ))
        await message.answer(
            f"⏳ {rl_result.denial_message}",
        )
        return

    # ── Plan-based AI daily limit ─────────────────────────────────────
    _tenant_id2 = db_user.tenant_id if db_user else None
    if _tenant_id2 is not None:
        try:
            from core.services.usage_service import check_ai_limit

            _plan2 = data.get("tenant_plan")
            _ai_check2 = await check_ai_limit(_tenant_id2, _plan2)
            if not _ai_check2.allowed:
                await message.answer(f"⚠️ {_ai_check2.reason}")
                return
        except Exception:
            pass  # fail open

    # ── Prompt injection detection ────────────────────────────────────
    from core.security.prompt_sanitizer import scan_prompt

    scan = scan_prompt(text)
    if scan.risk_level.value != "none":
        asyncio.create_task(_log_suspicious_prompt(
            user_id=user_id,
            text=text,
            risk_level=scan.risk_level.value,
            matched_patterns=scan.matched_patterns,
            tenant_id=db_user.tenant_id if db_user else None,
            db_session=data.get("db_session"),
        ))
    if scan.blocked:
        log.warning(
            "prompt_injection_blocked",
            user_id=user_id,
            patterns=scan.matched_patterns,
        )
        await message.answer(
            "Kechirasiz, bu turdagi so'rovga javob bera olmayman.\n"
            "Stretch potoloklar haqida savol bering! 😊",
        )
        return
    text = scan.sanitized_text

    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # ── Resolve tenant-specific system prompt ─────────────────────────────
    db_session = data.get("db_session")
    tenant_prompt, tenant_kb = (
        await get_tenant_ai_config(db_session, db_user.tenant_id)
        if db_user and db_session
        else (None, None)
    )
    system_prompt = build_system_prompt(tenant_prompt, tenant_kb)

    # ── Append tenant knowledge base entries ───────────────────────────
    from core.services.ai_knowledge_service import get_tenant_knowledge_block

    _tenant_id = db_user.tenant_id if db_user else None
    kb_block = await get_tenant_knowledge_block(_tenant_id, text)
    if kb_block:
        system_prompt = system_prompt + kb_block

    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)
    _has_history = bool(history)

    # ── AI response cache ─────────────────────────────────────────────
    from core.services.ai_cache_service import get_cached_response, store_response

    _cache_hit = False
    cached = await get_cached_response(_tenant_id, text, has_history=_has_history)
    if cached is not None:
        result = cached
        _cache_hit = True
        asyncio.create_task(_ai_stats_incr("cache_hit", bot_id=_bot_id))
    else:
        asyncio.create_task(_ai_stats_incr("cache_miss", bot_id=_bot_id))

    if not _cache_hit:
        try:
            result = await _call_ai(text, history, context_block, system_prompt=system_prompt)
        except Exception:
            log.exception("ai_call_failed", user_id=user_id)
            await _store_user_message_only(
                user_id=user_id,
                user_text=text,
                current_messages=history,
            )
            await message.answer(_FAILSAFE_TEXT, reply_markup=_FAILSAFE_KB)
            return

    try:
        intent = str(result.get("intent", "other"))
        reply_text = str(result.get("reply", "")).strip()
        extracted: dict[str, Any] = result.get("extracted") or {}
        lead_temperature, closing_confidence = _parse_ai_scoring(result)
        if not reply_text:
            raise ValueError("empty AI reply")
    except Exception:
        log.exception("ai_call_failed", user_id=user_id)
        await _store_user_message_only(
            user_id=user_id,
            user_text=text,
            current_messages=history,
        )
        await message.answer(_FAILSAFE_TEXT, reply_markup=_FAILSAFE_KB)
        return

    if not _cache_hit:
        asyncio.create_task(store_response(
            _tenant_id, text, result, has_history=_has_history,
        ))

    await message.answer(reply_text)

    _closer_score = await _get_lead_score(user_id, bot_id=_bot_id)

    try:
        from apps.bot.handlers.private.sales_closer import attempt_close
        await attempt_close(
            message, state, user_id,
            intent=intent,
            score=_closer_score,
            closing_confidence=closing_confidence,
        )
    except Exception:
        pass

    # Escalate HOT leads to tenant admin group (fire-and-forget)
    asyncio.create_task(_maybe_escalate(
        message, user_id,
        intent=intent, score=_closer_score,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
        last_message=text[:200],
        data=data,
    ))

    await _persist_exchange(
        user_id=user_id,
        user_text=text,
        assistant_text=reply_text,
        intent=intent,
        extracted=extracted,
        current_profile=profile,
        current_messages=history,
        current_summary=summary,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
    )
    if lead_temperature is not None or closing_confidence is not None:
        asyncio.create_task(
            _update_lead_ai_scoring(
                user_id=user_id,
                lead_temperature=lead_temperature,
                closing_confidence=closing_confidence,
            )
        )
    _fsm_for_mem = await state.get_data()
    asyncio.create_task(
        _update_ai_memory_from_interaction(
            user_id, text=text, fsm_data=_fsm_for_mem,
            first_name=message.from_user.first_name if message.from_user else None,
            bot_id=_bot_id,
        )
    )
    log.info(
        "ai_reply_sent",
        user_id=user_id,
        intent=intent,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
    )


# ── Inline-button callbacks ─────────────────────────────────────────────────

@router.callback_query(F.data == "ai:start_price")
async def cb_start_price(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Kick off the pricing FSM from an AI-generated inline button."""
    await callback.answer()
    if callback.message:
        await start_pricing_flow(callback.message, state)


@router.callback_query(F.data == "ai:show_catalog")
async def cb_show_catalog(callback: CallbackQuery, **data: object) -> None:
    """Show the catalog section list from an AI-generated inline button."""
    await callback.answer()
    if callback.message:
        await callback.message.answer(_CATALOG_INTRO, reply_markup=catalog_list_keyboard())
