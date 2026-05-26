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
from apps.bot.ai.system_prompt import _parse_ai_scoring
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
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
    detect_objection_full,
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


# ── Lead signal extraction (fire-and-forget) ─────────────────────────────────


async def _run_orchestrator(user_id: int, text: str) -> None:
    """Run agent orchestrator pipeline and persist trace (fire-and-forget)."""
    try:
        settings = get_settings()
        biz = settings.business
        if not biz.agent_response_orchestrator_enabled:
            return

        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        mem: dict = {"followup_enabled": True, "memory_data": {}}
        try:
            factory = get_session_factory()
            async with factory() as session:
                from core.services.agent_memory_service import AgentMemoryService
                svc = AgentMemoryService(session)
                db_mem = await svc.get_or_create(user_id)
                mem = {
                    "followup_enabled": db_mem.followup_enabled,
                    "followup_count": db_mem.followup_count,
                    "lead_temperature": db_mem.lead_temperature,
                    "phone_masked": db_mem.phone_masked,
                    "area_m2": db_mem.area_m2,
                    "memory_data": dict(db_mem.memory_data or {}),
                    "telegram_user_id": user_id,
                }
        except Exception:
            pass

        payload = AgentResponseOrchestrator.run_pipeline(
            memory=mem, text=text,
        )

        if biz.agent_response_orchestrator_trace_enabled:
            try:
                factory = get_session_factory()
                async with factory() as session:
                    from core.services.agent_memory_service import AgentMemoryService
                    svc = AgentMemoryService(session)
                    db_mem = await svc.get_or_create(user_id)
                    md = dict(db_mem.memory_data or {})
                    md = AgentResponseOrchestrator.persist_trace(md, payload)
                    db_mem.memory_data = md
                    await session.commit()
            except Exception:
                pass
    except Exception:
        log.debug("orchestrator_run_failed", user_id=user_id)


async def _process_lead_signal(user_id: int, text: str) -> None:
    """Extract intent/objection/urgency signals and persist to agent memory."""
    try:
        settings = get_settings()
        if not settings.business.agent_lead_signal_enabled:
            return

        from core.services.lead_signal_service import LeadSignalService

        signal = LeadSignalService.extract_signals(text)

        if signal.confidence_score < settings.business.agent_lead_signal_min_confidence:
            return

        factory = get_session_factory()
        async with factory() as session:
            from core.services.agent_memory_service import AgentMemoryService

            mem_svc = AgentMemoryService(session)
            mem = await mem_svc.get_or_create(user_id)

            md = dict(mem.memory_data or {})
            md = LeadSignalService.update_memory_from_signal(md, signal)
            mem.memory_data = md

            if signal.area_m2 is not None:
                mem.area_m2 = signal.area_m2

            if signal.should_disable_followup:
                mem.followup_enabled = False
                mem.stop_reason = "user_stop_signal"
                from core.services.followup_scheduler_service import FollowupSchedulerService
                fu_svc = FollowupSchedulerService(session)
                await fu_svc.cancel_all_pending(user_id, "user_stop_signal")

            await session.commit()
    except Exception:
        log.debug("lead_signal_processing_failed", user_id=user_id)

# ── Per-user AI rate limit ────────────────────────────────────────────────

_AI_DAILY_LIMIT = 100


async def _check_ai_rate_limit(user_id: int) -> bool:
    """Return True if user is within daily AI limit, False if exceeded."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()
        key = CacheKeys.ai_rate_limit_daily(user_id)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, CacheTTL.AI_RATE_LIMIT_DAILY)
        return count <= _AI_DAILY_LIMIT
    except Exception:
        return True  # fail-open: allow on Redis error


# ── Auto-reply decision layer ──────────────────────────────────────────────


async def _try_auto_reply(
    message: Message,
    state: FSMContext,
    user_id: int,
    text: str,
) -> bool:
    """Try to auto-reply with a template instead of calling OpenAI.

    Returns True if auto-reply was sent (caller should return early).
    Returns False if OpenAI should be called as usual.
    """
    import json

    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()

        # Load signals
        mem = await _load_ai_memory(user_id) or {}
        score = await _get_lead_score(user_id)

        # Consecutive auto-reply counter
        raw_consec = await redis.get(CacheKeys.auto_reply_consecutive(user_id))
        consecutive = int(raw_consec) if raw_consec else 0

        # Health score (lightweight — catch errors)
        health_score = 50
        try:
            from core.services.conversation_intelligence_service import (
                analyze_conversation,
            )
            ci = analyze_conversation(
                score=score,
                last_objection=mem.get("last_objection"),
                phone_captured=bool(mem.get("phone_captured")),
                area_m2=float(mem["area_m2"]) if mem.get("area_m2") else None,
                minutes_since_last_activity=0,  # user just sent a message
                follow_up_count=0,
                lead_temperature=mem.get("lead_temperature"),
                closing_confidence=mem.get("closing_confidence"),
                buyer_type=mem.get("buyer_type"),
                has_district=bool(mem.get("district")),
                current_stage="NEW",
            )
            health_score = ci.health_score
        except Exception:
            pass

        from core.services.auto_sales_service import (
            build_escalation_alert,
            decide_auto_reply,
            generate_auto_reply,
            should_escalate,
        )

        # 1. Check escalation first
        esc = should_escalate(
            last_objection=mem.get("last_objection"),
            objection_severity=mem.get("last_objection_severity"),
            consecutive_auto_replies=consecutive,
            health_score=health_score,
            negotiation_escalated=bool(mem.get("negotiation_escalated")),
            follow_up_count=0,
            score=score,
            closing_confidence=mem.get("closing_confidence"),
        )

        if esc.should_escalate:
            # Send escalation alert to admin group (non-blocking)
            settings = get_settings()
            admin_group_id = settings.bot.admin_group_id
            if admin_group_id and message.bot:
                dedup_key = CacheKeys.auto_sales_escalation(user_id)
                was_set = await redis.set(
                    dedup_key, "1",
                    ttl=CacheTTL.AUTO_SALES_ESCALATION,
                    nx=True,
                )
                if was_set:
                    from shared.utils.telegram_send import safe_send_message
                    alert = build_escalation_alert(
                        lead_id=user_id,
                        lead_name=mem.get("name", "?"),
                        lead_phone=mem.get("phone", "\u2014"),
                        reason_uz=esc.reason_uz,
                        last_message=text[:120],
                        suggested_action_uz=esc.suggested_action_uz,
                        urgency=esc.urgency,
                    )
                    asyncio.create_task(
                        safe_send_message(message.bot, admin_group_id, alert)
                    )
            # Don't block the response — fall through to OpenAI
            return False

        # 2. Check auto-reply eligibility
        decision = decide_auto_reply(
            score=score,
            health_score=health_score,
            last_objection=mem.get("last_objection"),
            objection_severity=mem.get("last_objection_severity"),
            consecutive_auto_replies=consecutive,
            negotiation_escalated=bool(mem.get("negotiation_escalated")),
            lead_temperature=mem.get("lead_temperature"),
            closing_confidence=mem.get("closing_confidence"),
        )

        if not decision.auto_reply_allowed:
            return False

        # 3. Detect simple intent from text for template matching
        intent = _detect_simple_intent(text)
        if intent is None:
            # No clear template match — let OpenAI handle it
            return False

        # 4. Generate template reply
        reply = generate_auto_reply(
            intent=intent,
            buyer_type=mem.get("buyer_type"),
            has_area=bool(mem.get("area_m2")),
            has_phone=bool(mem.get("phone_captured")),
            has_district=bool(mem.get("district")),
            last_objection=mem.get("last_objection"),
        )

        # 5. Send auto-reply
        await message.answer(reply.reply_text, reply_markup=_ai_keyboard())

        # 6. Increment consecutive counter
        key = CacheKeys.auto_reply_consecutive(user_id)
        new_count = await redis.incr(key)
        if new_count == 1:
            await redis.expire(key, CacheTTL.AUTO_REPLY_CONSECUTIVE)

        # 7. Log auto-reply to Redis
        log_data = json.dumps({
            "reply_type": reply.reply_type,
            "confidence": decision.confidence,
            "ts": int(__import__("time").time()),
        })
        await redis.set(
            CacheKeys.auto_reply_log(user_id),
            log_data,
            ttl=CacheTTL.AUTO_REPLY_LOG,
        )

        # Log tactic outcome for outcome-based learning
        import asyncio as _aio
        from core.services.tactic_outcome_logger import log_tactic_outcome
        _temp = "hot" if score >= 60 else ("warm" if score >= 30 else "cold")
        _aio.create_task(log_tactic_outcome(
            event_type="auto_reply",
            tactic_name=reply.reply_type,
            user_id=user_id,
            lead_score_at_time=score,
            lead_temperature_at_time=_temp,
        ))

        log.info(
            "auto_reply_sent",
            user_id=user_id,
            reply_type=reply.reply_type,
            confidence=decision.confidence,
            consecutive=new_count,
        )

        return True

    except Exception:
        log.debug("auto_reply_check_failed", user_id=user_id)
        return False


def _detect_simple_intent(text: str) -> str | None:
    """Detect a simple intent from user text for auto-reply templates.

    Returns intent key or None if text requires OpenAI.
    """
    t = text.lower().strip()

    _PRICE_WORDS = frozenset({
        "narx", "qancha", "necha pul", "baho", "qimmat", "arzon",
        "narxi qancha", "narxi", "qanchaga", "nechpul",
    })
    _MATERIAL_WORDS = frozenset({
        "material", "rang", "dizayn", "qanday", "variant",
        "tekstura", "mat", "glossy", "satin", "rangli",
    })
    _PACKAGE_WORDS = frozenset({
        "paket", "tayyor", "komplekt", "to'plam", "premium", "standart",
    })

    for kw in _PRICE_WORDS:
        if kw in t:
            return "price"

    for kw in _MATERIAL_WORDS:
        if kw in t:
            return "material"

    for kw in _PACKAGE_WORDS:
        if kw in t:
            return "package"

    return None


async def _reset_auto_reply_counter(user_id: int) -> None:
    """Reset consecutive auto-reply counter after an OpenAI response."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys
        await get_redis().delete(CacheKeys.auto_reply_consecutive(user_id))
    except Exception:
        pass


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
            bot=message.bot, chat_id=message.chat.id, user_id=user_id,
            nonce=_nonce, storage=state.storage, state_key=state.key,
        )

    await state.update_data(last_user_message=text[:200])

    if _is_measurement_request(text):
        asyncio.create_task(_ai_stats_incr("orders_started"))
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 25))
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    if _is_catalog_request(text):
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 5))
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

    _obj_det = detect_objection_full(text)
    if _obj_det:
        await _handle_objection(_obj_det.objection_type, message, state, user_id, severity=_obj_det.severity)
        return

    _combo = parse_combo(text)
    _price_area = _combo["area"]
    if _is_price_query(text) or _price_area is not None:
        if _price_area is not None:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 15 + (10 if _combo["district"] else 0)))
            await _show_price_upsell(
                message, state, _price_area,
                district=_combo["district"], design=_combo["design"],
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
                await message.answer(
                    "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                    reply_markup=_ai_keyboard(),
                )
            else:
                await message.answer(_PRICE_ASK_DESIGN_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Auto-reply check (skip OpenAI if template matches) ─────────
    if user_id and await _try_auto_reply(message, state, user_id, text):
        return

    if user_id and not await _check_ai_rate_limit(user_id):
        await message.answer(
            "Kunlik AI limit tugadi. Ertaga yana urinib ko'ring.",
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
        await _store_user_message_only(
            user_id=user_id, user_text=text, current_messages=history
        )
        await message.answer(_FAILSAFE_TEXT, reply_markup=_ai_keyboard())
        return

    # Reset consecutive auto-reply counter after OpenAI response
    asyncio.create_task(_reset_auto_reply_counter(user_id))

    await message.answer(reply_text, reply_markup=_ai_keyboard())

    try:
        from apps.bot.handlers.private.sales_closer import attempt_close
        _closer_score = await _get_lead_score(user_id)
        await attempt_close(
            message, state, user_id,
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
            user_id, text=text, fsm_data=_fsm_for_mem,
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
async def handle_ai_message(
    message: Message, state: FSMContext, **data: object
) -> None:
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
            bot=message.bot, chat_id=message.chat.id, user_id=user_id,
            nonce=_nonce, storage=state.storage, state_key=state.key,
        )

    if _is_measurement_request(text):
        asyncio.create_task(_ai_stats_incr("orders_started"))
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 25))
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    if _is_catalog_request(text):
        if user_id:
            asyncio.create_task(_add_lead_score(user_id, 5))
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

    _obj_det = detect_objection_full(text)
    if _obj_det:
        await _handle_objection(_obj_det.objection_type, message, state, user_id, severity=_obj_det.severity)
        return

    _combo = parse_combo(text)
    area = _combo["area"]
    if _is_price_query(text) or area is not None:
        if area is not None:
            if user_id:
                asyncio.create_task(_add_lead_score(user_id, 15 + (10 if _combo["district"] else 0)))
            await _show_price_upsell(
                message, state, area,
                district=_combo["district"], design=_combo["design"],
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
                await message.answer(
                    "Xonangiz taxminan necha m²?\nMasalan: 20 m² yoki 5x3",
                    reply_markup=_ai_keyboard(),
                )
            else:
                await message.answer(_PRICE_ASK_DESIGN_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Auto-reply check (skip OpenAI if template matches) ─────────
    if user_id and await _try_auto_reply(message, state, user_id, text):
        return

    if user_id and not await _check_ai_rate_limit(user_id):
        await message.answer(
            "Kunlik AI limit tugadi. Ertaga yana urinib ko'ring.",
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
            message, state, user_id,
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
            user_id, text=text, fsm_data=_fsm_for_mem,
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
