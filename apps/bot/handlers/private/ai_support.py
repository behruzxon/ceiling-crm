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

  ai_states.py              - FSM states, keyboards, text constants
  ai_detection.py           - Intent / trigger detection, text parsing
  ai_memory.py              - Redis AI memory + stats
  ai_scoring.py             - Lead scoring + objection detection / handling
  ai_openai.py              - OpenAI integration + conversation DB helpers
  ai_notifications.py       - Admin notification orchestration
  ai_followups.py           - Async delayed follow-up tasks
  ai_pricing_helpers.py     - Price display helpers
  ai_support_agent.py       - Agent pipeline (orchestrator + lead signal)
  ai_support_auto_reply.py  - Auto-reply decision layer + rate limiting
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

from apps.bot.ai.system_prompt import _parse_ai_scoring
from apps.bot.handlers.private.ai_detection import (  # noqa: F401
    _GENERIC_CONFIRMATIONS,
    _build_smart_catalog_response,
    _build_warranty_quality_reply,
    _catalog_link_kb,
    _detect_catalog_context,
    _detect_room_type,
    _is_catalog_request,
    _is_greeting,
    _is_measurement_request,
    _is_operator_request,
    _is_price_query,
    _is_warranty_quality_question,
    _normalize_room,
    _parse_area,
    _room_design_text,
    detect_district,
    is_valid_name,
    normalize_name,
    parse_combo,
)
from apps.bot.handlers.private.ai_followups import (
    _photo_followup_task,
    _refresh_ai_followup_nonce,
    _schedule_ai_followup,
    _schedule_catalog_followup,
)
from apps.bot.handlers.private.ai_memory import (  # noqa: F401
    _ai_stats_count_user,
    _ai_stats_incr,
    _build_greeting_from_memory,
    _load_ai_memory,
    _save_ai_memory,
    _update_ai_memory_from_interaction,
)
from apps.bot.handlers.private.ai_notifications import (
    _notify_ai_lead_collected,
    _notify_phone_captured,
    _notify_warm_interest,
    _update_lead_ai_scoring,
)
from apps.bot.handlers.private.ai_openai import (
    _build_context_block,
    _call_ai,
    _load_context,
    _persist_exchange,
    _store_user_message_only,
    clear_ai_conversation,  # noqa: F401 — re-exported for support.py
)
from apps.bot.handlers.private.ai_pricing_helpers import (
    _show_price_upsell,
)
from apps.bot.handlers.private.ai_scoring import (  # noqa: F401
    _add_lead_score,
    _get_lead_score,
    _handle_objection,
    classify_score,
    detect_objection,
    detect_objection_full,
)

# ── Sibling module imports ──────────────────────────────────────────────────
from apps.bot.handlers.private.ai_states import (  # noqa: F401
    _AI_HELP_TEXT,
    _AI_MODE_STATUS,
    _AI_OPERATOR_PROMPT,
    _AI_PRICE_PROMPT,
    _AI_QUICK_BUTTONS,
    _AI_RATE_LIMIT_TEXT,
    _AI_RESET_SUCCESS,
    _AI_ROOM_ADVICE_PROMPT,
    _AI_UNAVAILABLE_TEXT,
    _CANCEL_PHONE,
    _CATALOG_INTRO,
    _CATALOG_SOFT_CTA,
    _EXIT_TEXTS,
    _FAILSAFE_KB,
    _FAILSAFE_TEXT,
    _NEUTRAL_REPLY,
    _PRICE_ASK_DESIGN_TEXT,
    BTN_AI_CATALOG,
    BTN_AI_HELP,
    BTN_AI_OPERATOR,
    BTN_AI_PRICE,
    BTN_AI_RESET,
    AiSupportStates,
    _ai_keyboard,
    _phone_request_keyboard,
)
from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.main_menu import BTN_AI, main_menu_keyboard
from core.services.catalog_link_resolver_service import (
    resolve_catalog_link as _resolve_catalog_link,
)
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger
from shared.utils.phone import extract_phone_from_text
from shared.utils.text_normalization import (
    latinize_uz_cyrillic as _latinize_uz_cyrillic,
)

log = get_logger(__name__)
router = Router(name="private:ai_support")


# Extracted module imports (agent pipeline + auto-reply)
from apps.bot.handlers.private.ai_support_agent import (  # noqa: F401, E402
    _process_lead_signal,
    _run_orchestrator,
)
from apps.bot.handlers.private.ai_support_auto_reply import (  # noqa: F401, E402
    _check_ai_rate_limit,
    _detect_simple_intent,
    _reset_auto_reply_counter,
    _try_auto_reply,
)

# ── Explicit AI mode — entry ────────────────────────────────────────────────


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == BTN_AI)
async def cmd_ai_start(message: Message, state: FSMContext, **data: object) -> None:
    """Enter dedicated AI chat mode (private only; redirect groups to DM)."""
    if message.from_user is None:
        return
    if message.chat.type != "private":
        settings = get_settings()
        bot_username = settings.bot.username or "bot"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Madina bilan suhbat",
                        url=f"https://t.me/{bot_username}?start=ai",
                    )
                ]
            ]
        )
        await message.answer(
            "🤖 AI yordamchisi faqat shaxsiy chatda ishlaydi. "
            "Quyidagi tugma orqali bot bilan to'g'ridan-to'g'ri yozing:",
            reply_markup=kb,
        )
        return
    user_id = message.from_user.id
    _mem = await _load_ai_memory(user_id)

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

_NAME_REJECT_KEYWORDS: frozenset[str] = frozenset(
    {
        "zakaz",
        "buyurtma",
        "narx",
        "qancha",
        "nech",
        "pul",
        "katalog",
        "rasm",
        "dizayn",
        "variant",
        "operator",
        "telefon",
        "aloqa",
        "tuman",
        "m2",
        "kv",
        "kvadrat",
    }
)


@router.message(
    StateFilter(AiSupportStates.waiting_for_name),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_name_input(message: Message, state: FSMContext, **data: object) -> None:
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
                    message.from_user.id, text=text, fsm_data={"user_name": name}
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
async def handle_district_input(message: Message, state: FSMContext, **data: object) -> None:
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
async def handle_phone_contact(message: Message, state: FSMContext, **data: object) -> None:
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
    _lead_score = 0
    if _phone_user_id:
        _lead_score = await _add_lead_score(_phone_user_id, 40)
    await state.update_data(price_phone=phone)
    await state.set_state(AiSupportStates.waiting_for_ai_question)
    await message.answer(
        "Rahmat 🙂\n"
        "Ma'lumotlaringiz qabul qilindi.\n"
        "Mutaxassisimiz tez orada siz bilan bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Boshqa savollaringiz bormi?", reply_markup=_ai_keyboard())
    asyncio.create_task(_ai_stats_incr("phones_received"))
    asyncio.create_task(_ai_stats_incr(f"lead_{classify_score(_lead_score)}"))
    if _phone_user_id:
        _fsm_snap = dict(fsm_data)

        async def _mark_phone_captured(uid: int = _phone_user_id, snap: dict = _fsm_snap) -> None:
            mem = await _load_ai_memory(uid)
            mem["phone_captured"] = True
            if not mem.get("district") and snap.get("price_district"):
                mem["district"] = snap["price_district"]
            if not mem.get("area_m2") and snap.get("price_area"):
                mem["area_m2"] = snap["price_area"]
            await _save_ai_memory(uid, mem)
            try:
                from infrastructure.cache.client import get_redis
                from infrastructure.cache.keys import CacheKeys, CacheTTL

                redis = get_redis()
                fu_state = (await redis.get_json(CacheKeys.ai_followup_state(uid))) or {}
                fu_state["lead_created"] = True
                await redis.set_json(
                    CacheKeys.ai_followup_state(uid),
                    fu_state,
                    ttl=CacheTTL.AI_FOLLOWUP_STATE,
                )
            except Exception:
                pass

        asyncio.create_task(_mark_phone_captured())

    _ai_mem = await _load_ai_memory(_phone_user_id) if _phone_user_id else {}
    _resolved_lead_id: int | None = None
    if _phone_user_id:
        try:
            factory = get_session_factory()
            async with factory() as _ld_sess:
                from infrastructure.database.repositories.lead_repo import PostgresLeadRepository

                _ld_list = await PostgresLeadRepository(_ld_sess).list_by_user(
                    _phone_user_id, limit=1
                )
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
async def handle_phone_input(message: Message, state: FSMContext, **data: object) -> None:
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
            reply_markup=(
                _phone_request_keyboard() if message.chat.type == "private" else _ai_keyboard()
            ),
        )
        return
    await _complete_phone_step(message, state, phone)


# ── AI exit handlers ────────────────────────────────────────────────────────


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text.in_(_EXIT_TEXTS),
)
async def handle_ai_exit(message: Message, state: FSMContext, **data: object) -> None:
    """Exit AI mode and return to main menu."""
    await state.clear()
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())


@router.message(StateFilter(AiSupportStates.waiting_for_ai_question), Command("ai_off"))
async def handle_ai_off(message: Message, state: FSMContext, **data: object) -> None:
    """Exit AI mode via /ai_off command."""
    await state.clear()
    await message.answer("🤖 AI rejim o'chirildi.", reply_markup=main_menu_keyboard())


# ── /ai_help & /ai_reset commands ──────────────────────────────────────────


@router.message(Command("ai_help"))
async def cmd_ai_help(message: Message, state: FSMContext, **data: object) -> None:
    """Show AI capabilities and usage examples."""
    await message.answer(_AI_HELP_TEXT, parse_mode="HTML", reply_markup=_ai_keyboard())


@router.message(Command("ai_reset"))
async def cmd_ai_reset(message: Message, state: FSMContext, **data: object) -> None:
    """Clear AI conversation memory (keeps CRM data)."""
    if message.from_user is None:
        return
    try:
        await clear_ai_conversation(message.from_user.id)
        await state.clear()
        await state.set_state(AiSupportStates.waiting_for_ai_question)
    except Exception:
        pass
    await message.answer(_AI_RESET_SUCCESS, reply_markup=_ai_keyboard())


# ── Quick button handlers ──────────────────────────────────────────────────


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text == BTN_AI_HELP,
)
async def handle_ai_help_btn(message: Message, state: FSMContext, **data: object) -> None:
    """Quick button: show AI help."""
    await cmd_ai_help(message, state, **data)


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text == BTN_AI_RESET,
)
async def handle_ai_reset_btn(message: Message, state: FSMContext, **data: object) -> None:
    """Quick button: reset AI memory."""
    await cmd_ai_reset(message, state, **data)


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text == BTN_AI_PRICE,
)
async def handle_ai_price_btn(message: Message, state: FSMContext, **data: object) -> None:
    """Quick button: prompt for pricing input."""
    await message.answer(
        _AI_PRICE_PROMPT,
        parse_mode="HTML",
        reply_markup=_ai_keyboard(),
    )


# ── Catalog deep-link helper ────────────────────────────────────────────


def _build_catalog_link_kb(text: str) -> InlineKeyboardMarkup:
    """Return an inline keyboard for the catalog reply.

    Three shapes depending on resolver output:

    * High-confidence direct match → single URL button to the section.
    * ``needs_confirmation`` → callback buttons (``catalog_confirm:<key>``)
      plus a ``catalog_all`` fallback so the user picks the right one.
    * No match / generic ask → single URL button to the full catalog.
    """
    result = _resolve_catalog_link(text)

    if result.needs_confirmation and result.candidates:
        rows: list[list[InlineKeyboardButton]] = [
            [
                InlineKeyboardButton(
                    text=f"✅ {c.title}",
                    callback_data=f"catalog_confirm:{c.key}",
                )
            ]
            for c in result.candidates
        ]
        rows.append(
            [
                InlineKeyboardButton(
                    text="📂 To'liq katalog",
                    callback_data="catalog_all",
                )
            ]
        )
        return InlineKeyboardMarkup(inline_keyboard=rows)

    if result.matched and result.link is not None and result.link.url:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"📂 {result.link.title} katalogi",
                        url=result.link.url,
                    )
                ]
            ]
        )

    # No design alias matched (or section URL empty) — generic fallback.
    fallback = result.fallback_link
    if fallback is None or not fallback.url:
        return _catalog_link_kb()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 To'liq katalogimiz",
                    url=fallback.url,
                )
            ]
        ]
    )


def _catalog_intro_text_for(text: str) -> str:
    """Return a short intro line for the catalog reply.

    Uses the resolver's ``intro_text`` for direct / confirmation
    results, and falls back to the existing personalised generic
    smart-catalog text when no design is detected.
    """
    result = _resolve_catalog_link(text)
    if result.needs_confirmation:
        return result.confirmation_question or result.intro_text
    if result.matched and result.link is not None:
        return result.intro_text
    # No design detected — keep the existing personalised generic intro.
    room, design = _detect_catalog_context(text)
    return _build_smart_catalog_response(room, design)


# ── Deterministic price calculator (wired in Step CO) ──────────────────


async def _try_price_calculator(
    message: Message,
    state: FSMContext,
    text: str,
    user_id: int,
) -> bool:
    """Try deterministic price calculation. Returns True if handled."""
    try:
        from core.services.price_calculator_service import (
            PriceCalculatorService,
        )

        svc = PriceCalculatorService()
        resp = svc.extract_and_respond(text)
        if resp.estimate is not None:
            await message.answer(
                resp.user_text,
                parse_mode="HTML",
                reply_markup=_ai_keyboard(),
            )
            if resp.memory_payload and user_id:
                try:
                    fsm_data = await state.get_data()
                    fsm_data["last_price_estimate"] = resp.memory_payload
                    await state.update_data(**fsm_data)
                except Exception:
                    pass
            return True
    except Exception:
        pass
    return False


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text == BTN_AI_CATALOG,
)
async def handle_ai_catalog_btn(message: Message, state: FSMContext, **data: object) -> None:
    """Quick button: show catalog."""
    await message.answer(_CATALOG_INTRO, parse_mode="HTML", reply_markup=catalog_list_keyboard())


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text == BTN_AI_OPERATOR,
)
async def handle_ai_operator_btn(message: Message, state: FSMContext, **data: object) -> None:
    """Quick button: operator handoff with queue recording."""
    user_id = message.from_user.id if message.from_user else 0
    msg = await _try_operator_handoff(user_id, source="ai_button")
    await message.answer(msg, reply_markup=_ai_keyboard())


async def _try_operator_handoff(
    user_id: int,
    *,
    source: str = "ai_button",
    reason: str = "operator_requested",
) -> str:
    """Create handoff queue entry and return safe user message."""
    try:
        from core.services.crm_operator_handoff_service import (
            build_user_message,
        )
        from shared.config import get_settings

        settings = get_settings()
        if not settings.business.crm_operator_handoff_queue_enabled:
            return _AI_OPERATOR_PROMPT
        has_phone = False
        try:
            from apps.bot.handlers.private.ai_memory import (
                _load_ai_memory,
            )

            mem = await _load_ai_memory(user_id) or {}
            has_phone = bool(mem.get("phone_captured"))
        except Exception:
            pass
        return build_user_message(has_phone=has_phone)
    except Exception:
        return _AI_OPERATOR_PROMPT


# ── Photo funnel handlers ───────────────────────────────────────────────────


@router.message(
    StateFilter(AiSupportStates.waiting_photo),
    F.photo,
    F.chat.type == "private",
)
async def handle_photo_received(message: Message, state: FSMContext, **data: object) -> None:
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
async def handle_photo_state_text(message: Message, state: FSMContext, **data: object) -> None:
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
async def handle_room_input(message: Message, state: FSMContext, **data: object) -> None:
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
async def handle_area_photo_input(message: Message, state: FSMContext, **data: object) -> None:
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


# ── Explicit AI question handler ────────────────────────────────────────────


@router.message(
    StateFilter(AiSupportStates.waiting_for_ai_question),
    F.text,
    ~F.text.startswith("/"),
    ~F.text.in_(_EXIT_TEXTS),
)
async def handle_ai_question(message: Message, state: FSMContext, **data: object) -> None:
    """Answer questions with the AI service while in explicit AI mode."""
    text = _normalize_room(message.text or "")
    user_id = message.from_user.id if message.from_user else 0

    asyncio.create_task(_ai_stats_incr("messages_total"))
    if user_id:
        asyncio.create_task(_ai_stats_count_user(user_id))
        asyncio.create_task(_process_lead_signal(user_id, text))
        asyncio.create_task(_run_orchestrator(user_id, text))

    if user_id and _is_greeting(text):
        _mem = await _load_ai_memory(user_id)
        if _mem.get("name"):
            await message.answer(_build_greeting_from_memory(_mem), reply_markup=_ai_keyboard())
            return

    if message.bot and user_id and message.chat.type == "private":
        _nonce = await _refresh_ai_followup_nonce(user_id)
        _schedule_ai_followup(
            bot=message.bot,
            chat_id=message.chat.id,
            user_id=user_id,
            nonce=_nonce,
            storage=state.storage,
            state_key=state.key,
        )

    await state.update_data(last_user_message=text[:200])

    if _is_measurement_request(text):
        asyncio.create_task(_ai_stats_incr("orders_started"))
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 25))
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow

        await start_measurement_flow(message, state)
        return

    # Price-intent win: design names alone are in _CATALOG_TRIGGERS, so
    # a message like "gulli nech pul" / "гулли неч пул" would otherwise
    # route to the catalog branch. Skip catalog when the same text
    # carries a price keyword or an explicit area (checked on both the
    # raw Latin text and the latinized form for Cyrillic input).
    _early_combo = parse_combo(text)
    _latinized = _latinize_uz_cyrillic(text)
    _price_intent_present = (
        _is_price_query(text) or _is_price_query(_latinized) or _early_combo["area"] is not None
    )

    # Warranty / quality FAQ wins over catalog when no price intent —
    # "rasmiy kafolat" / "hammomga qo'yish mumkinmi" must NOT route
    # to a generic catalog link.
    if _is_warranty_quality_question(text) and not _price_intent_present:
        await message.answer(_build_warranty_quality_reply(text), reply_markup=_ai_keyboard())
        return

    if _is_catalog_request(text) and not _price_intent_present:
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 5))
        room, design = _detect_catalog_context(text)
        await message.answer(
            _catalog_intro_text_for(text),
            reply_markup=_build_catalog_link_kb(text),
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

    _obj_det = detect_objection_full(text)
    if _obj_det:
        await _handle_objection(
            _obj_det.objection_type, message, state, user_id, severity=_obj_det.severity
        )
        return

    _combo = parse_combo(text)
    _price_area = _combo["area"]
    if _is_price_query(text) or _price_area is not None:
        if _price_area is not None and _combo["design"]:
            if user_id:
                asyncio.create_task(
                    _add_lead_score(user_id, 15 + (10 if _combo["district"] else 0))
                )
            if await _try_price_calculator(message, state, text, user_id):
                return
        if _price_area is not None:
            if user_id:
                asyncio.create_task(
                    _add_lead_score(user_id, 15 + (10 if _combo["district"] else 0))
                )
            await _show_price_upsell(
                message,
                state,
                _price_area,
                district=_combo["district"],
                design=_combo["design"],
            )
        elif _combo["district"]:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10))
            await state.update_data(price_district=_combo["district"])
            await message.answer(
                f"📍 Tuman: {_combo['district']}\n\n"
                "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                reply_markup=_ai_keyboard(),
            )
        else:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10))
            if _combo["design"]:
                await state.update_data(price_design=_combo["design"])
                await message.answer(
                    "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                    reply_markup=_ai_keyboard(),
                )
            else:
                await message.answer(_PRICE_ASK_DESIGN_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Operator handoff via free text (real-language pack) ─────────
    if _is_operator_request(text):
        msg = await _try_operator_handoff(user_id, source="ai_text", reason="operator_requested")
        await message.answer(msg, reply_markup=_ai_keyboard())
        return

    # ── Auto-reply check (skip OpenAI if template matches) ─────────
    if user_id and await _try_auto_reply(message, state, user_id, text):
        return

    if user_id and not await _check_ai_rate_limit(user_id):
        await message.answer(
            _AI_RATE_LIMIT_TEXT,
            reply_markup=_ai_keyboard(),
        )
        return

    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)

    try:
        result = await _call_ai(text, history, context_block)
        intent = str(result.get("intent", "other"))
        reply_text = str(result.get("reply", "")).strip()
        extracted: dict[str, Any] = result.get("extracted") or {}
        lead_temperature, closing_confidence = _parse_ai_scoring(result)
        if not reply_text:
            raise ValueError("empty AI reply")
    except Exception:
        log.exception("ai_call_failed", user_id=user_id)
        await _store_user_message_only(user_id=user_id, user_text=text, current_messages=history)
        await message.answer(_FAILSAFE_TEXT, reply_markup=_ai_keyboard())
        return

    # Reset consecutive auto-reply counter after OpenAI response
    asyncio.create_task(_reset_auto_reply_counter(user_id))

    await message.answer(reply_text, reply_markup=_ai_keyboard())

    try:
        from apps.bot.handlers.private.sales_closer import attempt_close

        _closer_score = await _get_lead_score(user_id)
        await attempt_close(
            message,
            state,
            user_id,
            intent=intent,
            score=_closer_score,
            closing_confidence=closing_confidence,
        )
    except Exception:
        pass

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
            user_id,
            text=text,
            fsm_data=_fsm_for_mem,
            first_name=message.from_user.first_name if message.from_user else None,
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
async def handle_ai_message(message: Message, state: FSMContext, **data: object) -> None:
    """Route free-text DMs: dimension shortcut or AI reply with persistent memory."""
    text = message.text or ""
    user_id = message.from_user.id if message.from_user else 0

    asyncio.create_task(_ai_stats_incr("messages_total"))
    if user_id:
        asyncio.create_task(_ai_stats_count_user(user_id))
        asyncio.create_task(_process_lead_signal(user_id, text))
        asyncio.create_task(_run_orchestrator(user_id, text))

    if user_id and _is_greeting(text):
        _mem = await _load_ai_memory(user_id)
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
        _nonce = await _refresh_ai_followup_nonce(user_id)
        _schedule_ai_followup(
            bot=message.bot,
            chat_id=message.chat.id,
            user_id=user_id,
            nonce=_nonce,
            storage=state.storage,
            state_key=state.key,
        )

    if _is_measurement_request(text):
        asyncio.create_task(_ai_stats_incr("orders_started"))
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 25))
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow

        await start_measurement_flow(message, state)
        return

    # Price-intent win: see handle_ai_question for the same guard
    # (including the Cyrillic latinization fallback).
    _early_combo = parse_combo(text)
    _latinized = _latinize_uz_cyrillic(text)
    _price_intent_present = (
        _is_price_query(text) or _is_price_query(_latinized) or _early_combo["area"] is not None
    )

    # Warranty / quality FAQ wins over catalog when no price intent —
    # "rasmiy kafolat" / "hammomga qo'yish mumkinmi" must NOT route
    # to a generic catalog link.
    if _is_warranty_quality_question(text) and not _price_intent_present:
        await message.answer(_build_warranty_quality_reply(text), reply_markup=_ai_keyboard())
        return

    if _is_catalog_request(text) and not _price_intent_present:
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 5))
        room, design = _detect_catalog_context(text)
        await message.answer(
            _catalog_intro_text_for(text),
            reply_markup=_build_catalog_link_kb(text),
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

    # ── Stop-word detection: disable agent follow-ups ───────────────────
    from core.services.followup_scheduler_service import FollowupSchedulerService as _FuSvc

    if _FuSvc.is_stop_signal(text):
        log.info("stop_signal_received", user_id=user_id, text=text[:30])
        try:
            from core.services.agent_memory_service import AgentMemoryService as _MemSvc

            _stop_factory = get_session_factory()
            async with _stop_factory() as _stop_sess:
                await _MemSvc(_stop_sess).disable_followup(user_id, "user_opted_out")
                await _FuSvc(_stop_sess).cancel_all_pending(user_id, "user_opted_out")
                await _stop_sess.commit()
        except Exception:
            log.warning("stop_signal_handler_error", user_id=user_id)
        await message.answer("Tushunarli 😊 Sizga boshqa xabar yubormaymiz.")
        return

    _norm = (message.text or "").lower().strip()
    if _norm in _GENERIC_CONFIRMATIONS:
        await message.answer(_NEUTRAL_REPLY)
        return

    # ── Warranty / quality FAQ (real-language pack) ─────────────────
    if _is_warranty_quality_question(text):
        await message.answer(_build_warranty_quality_reply(text), reply_markup=_ai_keyboard())
        return

    _obj_det = detect_objection_full(text)
    if _obj_det:
        await _handle_objection(
            _obj_det.objection_type, message, state, user_id, severity=_obj_det.severity
        )
        return

    _combo = parse_combo(text)
    area = _combo["area"]
    if _is_price_query(text) or area is not None:
        if area is not None:
            if user_id:
                asyncio.create_task(
                    _add_lead_score(user_id, 15 + (10 if _combo["district"] else 0))
                )
            await _show_price_upsell(
                message,
                state,
                area,
                district=_combo["district"],
                design=_combo["design"],
            )
        elif _combo["district"]:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10))
            await state.update_data(price_district=_combo["district"])
            await message.answer(
                f"📍 Tuman: {_combo['district']}\n\n"
                "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                reply_markup=_ai_keyboard(),
            )
        else:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 10))
            if _combo["design"]:
                await state.update_data(price_design=_combo["design"])
                await message.answer(
                    "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                    reply_markup=_ai_keyboard(),
                )
            else:
                await message.answer(_PRICE_ASK_DESIGN_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Operator handoff via free text (real-language pack) ─────────
    if _is_operator_request(text):
        msg = await _try_operator_handoff(user_id, source="ai_text", reason="operator_requested")
        await message.answer(msg, reply_markup=_ai_keyboard())
        return

    # ── Auto-reply check (skip OpenAI if template matches) ─────────
    if user_id and await _try_auto_reply(message, state, user_id, text):
        return

    if user_id and not await _check_ai_rate_limit(user_id):
        await message.answer(
            _AI_RATE_LIMIT_TEXT,
        )
        return

    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)

    try:
        result = await _call_ai(text, history, context_block)
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

    # Reset consecutive auto-reply counter after OpenAI response
    asyncio.create_task(_reset_auto_reply_counter(user_id))

    await message.answer(reply_text)

    try:
        from apps.bot.handlers.private.sales_closer import attempt_close

        _closer_score = await _get_lead_score(user_id)
        await attempt_close(
            message,
            state,
            user_id,
            intent=intent,
            score=_closer_score,
            closing_confidence=closing_confidence,
        )
    except Exception:
        pass

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
            user_id,
            text=text,
            fsm_data=_fsm_for_mem,
            first_name=message.from_user.first_name if message.from_user else None,
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
async def cb_start_price(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
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
