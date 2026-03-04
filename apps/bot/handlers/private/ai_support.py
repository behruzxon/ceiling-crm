"""
AI-powered free-text handler for private DM chats.

Pipeline
--------
  Incoming text (no active FSM state)
    ├─ Dimension pair found (e.g. "5x4", "5м 4м") → jump to pricing FSM at design step
    ├─ Single bare number (e.g. "5")               → start pricing FSM at width step
    └─ General question                            → OpenAI JSON reply + intent keyboard

Memory pipeline (all DB ops are non-fatal)
  1. Load  : ai_user_memory.profile + ai_conversations.{last_messages, summary}
  2. Build : context block from profile + summary → second system message
  3. Call  : pass last 8 stored messages + current as conversation turns
  4. Store : append pair, trim to 12; upsert both tables
             every 10 turns → regenerate summary via separate AI call
  5. Fail  : if OpenAI unavailable, still store user message; reply with failsafe

OpenAI response schema
  {
    "intent":    "price|catalog|operator|measurement|faq|objection|other",
    "reply":     "<Uzbek reply text>",
    "extracted": {
      "interested_design": null,
      "last_dimensions":   null,
      "location":          null
    }
  }

Anti-repetition
  - No greeting when conversation history exists
  - Company intro suppressed after turn 1 (unless user asks)
  - CTA phrases rotate; last_intent stored in profile so AI picks a different one
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import sqlalchemy as sa
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from openai import AsyncOpenAI
from sqlalchemy.dialects.postgresql import insert as pg_insert

from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.main_menu import BTN_AI, main_menu_keyboard
from infrastructure.database.models.ai_conversation import AiConversationModel
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_notification_service
from apps.bot.ai.system_prompt import (
    _SYSTEM_PROMPT,
    _SUMMARY_SYSTEM,
    _VALID_TEMPS,
    _parse_ai_scoring,
)
from shared.config import get_settings
from shared.logging import get_logger
from shared.utils.phone import extract_phone_from_text

log = get_logger(__name__)
router = Router(name="private:ai_support")


# ── Measurement trigger detection ─────────────────────────────────────────────

_MEASUREMENT_TRIGGERS: frozenset[str] = frozenset({
    "yozib qo'y", "yozib qoʻy", "yozib qoy",
    "ha yozib", "bepul o'lchov", "bepul oʻlchov",
    "o'lchov kerak", "oʻlchov kerak",
    "o'lchov olish", "oʻlchov olish",
    "bepul olchov", "usta chaqir", "usta yuborin", "usta kerak",
})


def _is_measurement_request(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _MEASUREMENT_TRIGGERS)


# ── Catalog link shortcut ─────────────────────────────────────────────────────

_CATALOG_TRIGGERS: frozenset[str] = frozenset({
    # Catalog / portfolio / design intent
    "katalog", "katolog", "catalog", "portfolio",
    "variant", "dizayn", "design",
    "rasm", "foto", "surat", "namuna", "misol",
    "ko'rsat", "korsat", "tashla", "yubor", "kanal", "link",
    "ishlar", "dizaynlar", "работы", "фото", "каталог",
    # Design type names
    "gulli", "mramor", "naqsh", "hi tech", "hitech", "kosmos", "osmon",
    # Room types (when asking for designs)
    "mehmonxona", "mehmon xona", "zal",
    "yotoqxona", "oshxona", "hammom", "dush",
    "detskiy", "bolalar",
})


def _is_catalog_request(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _CATALOG_TRIGGERS)


_CATALOG_RESPONSE_TEXT = (
    "Albatta 🙂\n"
    "📌 Bizda **har qanday xona** uchun natijnoy potolok dizaynlarimiz bor:\n\n"
    "🏠 Mehmonxona\n"
    "🛏 Yotoqxona\n"
    "🍳 Oshxona\n"
    "🚿 Hammom\n"
    "👶 Bolalar xonasi\n\n"
    "👇 To'liq katalogni shu tugma orqali ko'rishingiz mumkin."
)

_CATALOG_FOLLOWUP_TEXT = (
    "Xonangiz taxminan **necha m²**?\n\n"
    "Masalan:\n"
    "• 20 m²\n"
    "• 5x3"
)


def _catalog_link_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📂 To'liq katalogimiz", url="https://t.me/vashpotolokuz"),
    ]])


# ── Room synonym normalisation ────────────────────────────────────────────────
# Maps user-written variants to the canonical Uzbek room name.
# Applied before the LLM so the model always receives a consistent term.

_ROOM_SYNONYMS: dict[str, list[str]] = {
    "mehmonxona": ["mehmon xona", "zal", "katta xona"],
    "yotoqxona":  ["yotoq xona", "spalnya"],
    "oshxona":    ["osh xona", "кухня"],
    "hammom":     ["vanna", "sanuzel"],
}


def _normalize_room(text: str) -> str:
    """Replace room synonyms with their canonical names (case-insensitive)."""
    lower = text.lower()
    for canonical, synonyms in _ROOM_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in lower:
                # Replace only the first occurrence, preserve surrounding text
                text = text.lower().replace(synonym, canonical, 1)
                return text
    return text


# ── Generic confirmation intercept ───────────────────────────────────────────
# These short replies carry no real intent — do not pass them to the LLM.
# The LLM tends to infer a design choice or fabricate a booking from them.

_GENERIC_CONFIRMATIONS: frozenset[str] = frozenset({
    "zo'r", "zor", "ok", "ha", "xo'p", "xop", "rahmat",
    "mayli", "bo'ldi", "boldi", "tushunarli", "yaxshi",
    "super", "ajoyib", "tushundim", "oke",
})

_NEUTRAL_REPLY = (
    "Tushunarli 🙂\n\n"
    "Narx hisoblaymizmi, katalog ko'ramizmi yoki bepul o'lchov kerakmi?"
)

# ── Price intent detection ────────────────────────────────────────────────────

_PRICE_KEYWORDS: frozenset[str] = frozenset({
    # Uzbek
    "narx", "narxlar", "narxi qancha", "qancha turadi", "qancha pul",
    "nech pul", "nech pul bo'ladi", "nechadan qilyapsizlar", "qanchadan",
    "nechadan", "hisoblab ber", "narxini ayt", "narxini hisobla",
    "narxini chiqar", "narx kalkulyator", "narx hisoblash",
    # Russian
    "сколько", "сколько стоит", "цена", "цены", "рассчитать цену",
})


def _is_price_query(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _PRICE_KEYWORDS)


# CASE A — price query with area: calculate totals per design type
def _build_price_calc(area: float) -> str:
    """Build a price calculation table for the given area in m²."""
    def _fmt(v: int) -> str:
        return f"{v:,}".replace(",", " ")

    a_str = f"{area:g}"
    return (
        f"{a_str} m² uchun taxminiy narx:\n\n"
        f"• Adnatonniy — {_fmt(int(area * 80_000))} so'm\n"
        f"• Hi Tech / Mramor / Naqsh / Kosmos / Osmon — {_fmt(int(area * 120_000))} so'm\n"
        f"• Qora UF — {_fmt(int(area * 140_000))} so'm\n"
        f"• Gulli — {_fmt(int(area * 120_000))}–{_fmt(int(area * 140_000))} so'm\n\n"
        "Qaysi turini tanlaysiz? 🙂"
    )


# CASE B — price query but no area detected
_PRICE_ASK_AREA_TEXT = (
    "Natijnoy potolok narxi xona maydoniga bog'liq 🙂\n\n"
    "Xona taxminan necha m²?\n\n"
    "Masalan:\n"
    "• 20 m²\n"
    "• 5x3"
)

# CASE C — price shown, upsell to free measurement
_UPSELL_ASK_DISTRICT = (
    "Agar xohlasangiz ustamiz kelib **bepul o'lchov qilib beradi** 🙂\n\n"
    "Qaysi tumandasiz?"
)


async def _show_price_upsell(
    message: Message,
    state: FSMContext,
    area: float,
) -> None:
    """Show price calculation then transition to lead-collection (district) state."""
    await message.answer(_build_price_calc(area), reply_markup=_ai_keyboard())
    await state.set_state(AiSupportStates.waiting_for_district)
    await state.update_data(price_area=area)
    await message.answer(_UPSELL_ASK_DISTRICT, reply_markup=_ai_keyboard())


# ── AI scoring → lead persistence (non-fatal, fire-and-forget) ───────────────

async def _update_lead_ai_scoring(
    *,
    user_id: int,
    lead_temperature: str | None,
    closing_confidence: float | None,
) -> None:
    """Find the latest lead for *user_id* and persist AI scoring. Never raises."""
    from shared.utils.lead_scoring import compute_next_followup
    try:
        factory = get_session_factory()
        async with factory() as session:
            from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
            repo = PostgresLeadRepository(session)
            leads = await repo.list_by_user(user_id, limit=1)
            if not leads:
                return
            lead = leads[0]
            next_fu = compute_next_followup(lead_temperature, closing_confidence)
            await repo.update_ai_scoring(
                lead.id,
                lead_temperature=lead_temperature,
                closing_confidence=closing_confidence,
                next_follow_up_at=next_fu,
            )
            await session.commit()
    except Exception:
        log.warning("update_lead_ai_scoring_failed", user_id=user_id)


# ── Phone capture helper ──────────────────────────────────────────────────────

async def _notify_phone_captured(
    *,
    phone: str,
    profile: dict[str, Any],
    from_user: Any,
    chat_type: str,
    chat_id: int,
) -> None:
    """Fire-and-forget admin alert when a phone is detected in free text."""
    try:
        name = profile.get("name") or (from_user.first_name if from_user else None)
        username = from_user.username if from_user else None
        user_id = from_user.id if from_user else None
        svc = get_lead_notification_service()
        await svc.notify_draft_lead(
            phone=phone,
            name=name,
            username=username,
            user_id=user_id,
            chat_type=chat_type,
            chat_id=chat_id,
        )
    except Exception:
        log.warning("phone_capture_notify_failed", phone=phone)


async def _notify_ai_lead_collected(
    *,
    phone: str,
    district: str,
    area: float | None,
    room: str | None,
    name: str | None,
    from_user: Any,
) -> None:
    """Fire-and-forget admin notification for AI-collected lead. Never raises."""
    try:
        svc = get_lead_notification_service()
        await svc.notify_ai_lead_collected(
            phone=phone,
            district=district,
            area=area,
            room=room,
            name=name,
            username=from_user.username if from_user else None,
            user_id=from_user.id if from_user else None,
        )
    except Exception:
        log.warning("notify_ai_lead_collected_failed", phone=phone)


async def _notify_warm_interest(
    *,
    topic: str,
    from_user: Any,
    name: str | None = None,
) -> None:
    """Fire-and-forget WARM lead interest notification. Never raises."""
    try:
        svc = get_lead_notification_service()
        await svc.notify_lead_interest(
            score="warm",
            name=name,
            username=from_user.username if from_user else None,
            user_id=from_user.id if from_user else None,
            topic=topic,
        )
    except Exception:
        log.warning("notify_warm_interest_failed", topic=topic)


# ── Explicit AI-mode FSM ──────────────────────────────────────────────────────

class AiSupportStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_ai_question = State()
    waiting_for_district = State()
    waiting_for_phone = State()


_EXIT_TEXTS: frozenset[str] = frozenset({"⬅️ Menyu", "🔙 Menyu"})


def _ai_keyboard() -> ReplyKeyboardMarkup:
    """Persistent exit button shown throughout the AI chat session."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Menyu")]],
        resize_keyboard=True,
    )


# ── Tuneable constants ────────────────────────────────────────────────────────

_MAX_MESSAGES = 12           # rolling window size stored in ai_conversations
_HISTORY_TO_SEND = 8         # how many messages to pass to OpenAI per call
_SUMMARY_EVERY_N_TURNS = 10  # regenerate summary every N user turns

# ── Dimension extraction ──────────────────────────────────────────────────────

from shared.utils.area_parser import parse_area as _parse_area


# ── OpenAI client (lazy singleton) ───────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        # AI_API_KEY overrides OPENAI_API_KEY when set
        api_key = (
            settings.ai.api_key.get_secret_value()
            if settings.ai.api_key
            else settings.openai.api_key.get_secret_value()
        )
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


# ── Context builder ───────────────────────────────────────────────────────────

def _build_context_block(
    profile: dict[str, Any],
    summary: str | None,
) -> str | None:
    """
    Build the per-request dynamic context injected as a second system message.
    Returns None when there is nothing useful to inject.
    """
    parts: list[str] = []

    profile_parts: list[str] = []
    if design := profile.get("interested_design"):
        profile_parts.append(f"qiziqayotgan dizayn: {design}")
    if dims := profile.get("last_dimensions"):
        profile_parts.append(f"so'nggi o'lcham: {dims}")
    if location := profile.get("location"):
        profile_parts.append(f"joylashuv: {location}")
    if profile_parts:
        parts.append("Profil: " + "; ".join(profile_parts))

    if summary:
        parts.append(f"Suhbat qisqartmasi: {summary}")

    # Last intent informs CTA rotation
    if last_intent := profile.get("last_intent"):
        parts.append(f"Oxirgi CTA turi: {last_intent}")

    if not parts:
        return None

    return "--- FOYDALANUVCHI KONTEKSTI ---\n" + "\n".join(parts)


# ── DB helpers (all non-fatal) ────────────────────────────────────────────────

async def _load_context(
    user_id: int,
) -> tuple[dict[str, Any], list[dict[str, str]], str | None]:
    """
    Load profile + conversation from DB.
    Returns (profile, messages, summary) — empty defaults on any error.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            mem = await session.get(AiMemoryModel, user_id)
            profile: dict[str, Any] = mem.profile if mem else {}

            conv = await session.get(AiConversationModel, user_id)
            messages: list[dict[str, str]] = conv.last_messages if conv else []
            summary: str | None = conv.summary if conv else None

        return profile, messages, summary
    except Exception:
        log.warning("ai_context_load_failed", user_id=user_id)
        return {}, [], None


async def _regenerate_summary(messages: list[dict[str, str]]) -> str:
    """
    Summarise the conversation in 2-4 lines.
    Raises on failure — caller decides whether to log and continue.
    """
    client = _get_client()
    settings = get_settings()
    history_text = "\n".join(
        f"{'Foydalanuvchi' if m['role'] == 'user' else 'Madina'}: {m['text']}"
        for m in messages
    )
    resp = await client.chat.completions.create(
        model=settings.ai.model,
        temperature=0.1,
        max_tokens=150,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user",   "content": history_text},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def _persist_exchange(
    *,
    user_id: int,
    user_text: str,
    assistant_text: str,
    intent: str,
    extracted: dict[str, Any],
    current_profile: dict[str, Any],
    current_messages: list[dict[str, str]],
    current_summary: str | None,
    lead_temperature: str | None = None,
    closing_confidence: float | None = None,
) -> None:
    """
    Upsert ai_user_memory + ai_conversations after a successful AI exchange.
    Every _SUMMARY_EVERY_N_TURNS turns the conversation summary is regenerated.
    All exceptions are swallowed — DB failure must never break the chat.
    """
    try:
        new_messages = (
            current_messages
            + [
                {"role": "user",      "text": user_text},
                {"role": "assistant", "text": assistant_text},
            ]
        )[-_MAX_MESSAGES:]

        turn_count = int(current_profile.get("turn_count", 0)) + 1

        # Optionally regenerate summary
        new_summary = current_summary
        if turn_count % _SUMMARY_EVERY_N_TURNS == 0:
            try:
                new_summary = await _regenerate_summary(new_messages)
                log.info("ai_summary_regenerated", user_id=user_id, turn=turn_count)
            except Exception:
                log.warning("ai_summary_regen_failed", user_id=user_id)

        # Merge AI-extracted profile fields (skip null / falsy values)
        new_profile: dict[str, Any] = {**current_profile}
        for field in ("interested_design", "last_dimensions", "location"):
            value = extracted.get(field)
            if value:
                new_profile[field] = value
        new_profile["last_intent"] = intent
        new_profile["turn_count"] = turn_count

        factory = get_session_factory()
        async with factory() as session:
            # ── ai_conversations upsert ───────────────────────────────────
            conv_values: dict[str, Any] = {
                "user_id": user_id,
                "last_messages": new_messages,
            }
            conv_set: dict[str, Any] = {
                "last_messages": new_messages,
                "updated_at": sa.func.now(),
            }
            if new_summary:
                conv_values["summary"] = new_summary
                if new_summary != current_summary:
                    conv_set["summary"] = new_summary
            if lead_temperature is not None:
                conv_values["lead_temperature"] = lead_temperature
                conv_set["lead_temperature"] = lead_temperature
            if closing_confidence is not None:
                conv_values["closing_confidence"] = closing_confidence
                conv_set["closing_confidence"] = closing_confidence

            await session.execute(
                pg_insert(AiConversationModel)
                .values(**conv_values)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_=conv_set,
                )
            )

            # ── ai_user_memory upsert ─────────────────────────────────────
            await session.execute(
                pg_insert(AiMemoryModel)
                .values(user_id=user_id, profile=new_profile)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "profile": new_profile,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.commit()

    except Exception:
        log.warning("ai_persist_exchange_failed", user_id=user_id)


async def clear_ai_conversation(user_id: int) -> None:
    """
    Reset the active conversation thread for a user (called on /start).

    Clears last_messages and summary in ai_conversations so the next AI
    interaction starts a fresh thread.  Does NOT touch ai_user_memory —
    the user's profile, design interests, dimensions, and location are kept.
    Non-fatal: any DB error is logged and swallowed.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                pg_insert(AiConversationModel)
                .values(user_id=user_id, last_messages=[], summary=None)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "last_messages": [],
                        "summary": None,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.commit()
        log.info("ai_conversation_cleared", user_id=user_id)
    except Exception:
        log.warning("ai_conversation_clear_failed", user_id=user_id)


async def _store_user_message_only(
    *,
    user_id: int,
    user_text: str,
    current_messages: list[dict[str, str]],
) -> None:
    """
    Persist the user's message even when the AI call fails so the next
    successful reply has conversation context.
    """
    try:
        new_messages = (
            current_messages + [{"role": "user", "text": user_text}]
        )[-_MAX_MESSAGES:]

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(
                pg_insert(AiConversationModel)
                .values(user_id=user_id, last_messages=new_messages)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "last_messages": new_messages,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.commit()
    except Exception:
        log.warning("ai_user_msg_store_failed", user_id=user_id)


# ── OpenAI call ───────────────────────────────────────────────────────────────

async def _call_ai(
    user_text: str,
    history: list[dict[str, str]],
    context_block: str | None,
) -> dict[str, Any]:
    """
    Build the messages array (system + context + history + current),
    call OpenAI, and return the parsed JSON dict.
    """
    settings = get_settings()
    client = _get_client()

    messages: list[dict[str, str]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
    ]
    # Dynamic context: profile data + summary + last intent (anti-repetition)
    if context_block:
        messages.append({"role": "system", "content": context_block})

    # Inject stored conversation history as real chat turns
    for msg in history[-_HISTORY_TO_SEND:]:
        messages.append({"role": msg["role"], "content": msg["text"]})

    # Current user message is NOT yet in history
    messages.append({"role": "user", "content": user_text})

    resp = await client.chat.completions.create(
        model=settings.ai.model,
        temperature=0.3,
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=messages,
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


_FAILSAFE_TEXT = (
    "⚠️ Kechirasiz, texnik nosozlik yuz berdi.\n\n"
    "Operatorga murojaat qilishingiz mumkin:"
)
_FAILSAFE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text="📞 Operator bilan bog'lanish",
            url="https://t.me/ceiling_manager",
        )],
    ]
)

_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"

# ── Explicit AI mode — entry / exit / question ────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == BTN_AI)
async def cmd_ai_start(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Enter dedicated AI chat mode (private only; redirect groups to DM)."""
    if message.from_user is None:
        return
    # AI FSM must never activate in group chats — redirect to DM instead.
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
    await state.clear()
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


@router.message(
    StateFilter(AiSupportStates.waiting_for_name),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_name_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Collect user's name (or detect price query) and enter AI question mode."""
    text = (message.text or "").strip()
    _area = _parse_area(text)

    if _is_price_query(text) or _area is not None:
        if _area is not None:
            await _show_price_upsell(message, state, _area)
        else:
            await state.set_state(AiSupportStates.waiting_for_ai_question)
            await message.answer(_PRICE_ASK_AREA_TEXT, reply_markup=_ai_keyboard())
        return

    # Name input
    await state.set_state(AiSupportStates.waiting_for_ai_question)
    await state.update_data(user_name=text)
    await message.answer(
        f"Juda yaxshi, {text} 🙂\n\n"
        "Sizga tezroq yordam berishim uchun kichkina savol:\n\n"
        "Potolok qaysi xona uchun kerak?\n\n"
        "🏠 Mehmonxona\n"
        "🛏 Yotoqxona\n"
        "🍳 Oshxona\n"
        "🚿 Hammom\n\n"
        "Va taxminan xona **necha m²**?",
        reply_markup=_ai_keyboard(),
    )


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
    await message.answer(
        "Telefon raqamingizni yozib qoldirsangiz ustamiz siz bilan bog'lanadi 🙂",
        reply_markup=_ai_keyboard(),
    )


@router.message(
    StateFilter(AiSupportStates.waiting_for_phone),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_phone_input(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Collect phone, confirm, and fire admin notification."""
    text = (message.text or "").strip()
    if text in _EXIT_TEXTS:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=main_menu_keyboard())
        return
    phone = extract_phone_from_text(text) or text
    fsm_data = await state.get_data()
    await state.set_state(AiSupportStates.waiting_for_ai_question)
    await message.answer(
        "Rahmat 🙂\n"
        "Ma'lumotlaringiz qabul qilindi.\n"
        "Mutaxassisimiz tez orada siz bilan bog'lanadi.",
        reply_markup=_ai_keyboard(),
    )
    asyncio.create_task(
        _notify_ai_lead_collected(
            phone=phone,
            district=fsm_data.get("price_district") or "",
            area=fsm_data.get("price_area"),
            room=fsm_data.get("price_room"),
            name=fsm_data.get("price_name") or fsm_data.get("user_name"),
            from_user=message.from_user,
        )
    )


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

    # Measurement shortcut — exit AI mode, start FSM immediately
    if _is_measurement_request(text):
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    # Catalog link shortcut — generic catalog/photo request
    if _is_catalog_request(text):
        await message.answer(
            _CATALOG_RESPONSE_TEXT,
            reply_markup=_catalog_link_kb(),
        )
        await message.answer(_CATALOG_FOLLOWUP_TEXT)
        fsm_data = await state.get_data()
        asyncio.create_task(
            _notify_warm_interest(
                topic="katalog / dizayn",
                from_user=message.from_user,
                name=fsm_data.get("user_name"),
            )
        )
        return

    # Generic confirmation — do not pass to LLM, reply neutrally
    _norm = (message.text or "").lower().strip()
    if _norm in _GENERIC_CONFIRMATIONS:
        await message.answer(_NEUTRAL_REPLY)
        return

    # Price intent or bare area — calculate and upsell
    _price_area = _parse_area(text)
    if _is_price_query(text) or _price_area is not None:
        if _price_area is not None:
            await _show_price_upsell(message, state, _price_area)
        else:
            await message.answer(_PRICE_ASK_AREA_TEXT, reply_markup=_ai_keyboard())
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

    # Reply with the AI text + persistent exit keyboard
    await message.answer(reply_text, reply_markup=_ai_keyboard())

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
    log.info(
        "ai_reply_sent",
        user_id=user_id,
        intent=intent,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
        mode="explicit",
    )


# ── Passive handler (default_state catch-all) ─────────────────────────────────

@router.message(
    F.chat.type == "private",
    F.text,
    ~F.text.startswith("/"),   # never intercept commands (/start, /help, /cancel …)
    StateFilter(default_state),
)
async def handle_ai_message(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Route free-text DMs: dimension shortcut or AI reply with persistent memory."""
    text = message.text or ""
    user_id = message.from_user.id if message.from_user else 0

    # ── Phone detection — alert admin if a new phone number is typed ──────
    detected_phone = extract_phone_from_text(text)
    if detected_phone:
        # Load profile to get name context (non-fatal)
        try:
            factory = get_session_factory()
            async with factory() as session:
                mem = await session.get(AiMemoryModel, user_id)
                _profile_for_phone: dict[str, Any] = mem.profile if mem else {}
        except Exception:
            _profile_for_phone = {}

        # Only notify if we haven't already stored a phone for this user
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

    # ── Measurement shortcut — start FSM immediately ──────────────────────
    if _is_measurement_request(text):
        from apps.bot.handlers.private.measurement_lead import start_measurement_flow
        await start_measurement_flow(message, state)
        return

    # ── Catalog link shortcut — generic catalog/photo request ────────────
    if _is_catalog_request(text):
        await message.answer(
            _CATALOG_RESPONSE_TEXT,
            reply_markup=_catalog_link_kb(),
        )
        await message.answer(_CATALOG_FOLLOWUP_TEXT)
        asyncio.create_task(
            _notify_warm_interest(
                topic="katalog / dizayn",
                from_user=message.from_user,
            )
        )
        return

    # ── Generic confirmation — reply neutrally, no LLM ───────────────────
    _norm = (message.text or "").lower().strip()
    if _norm in _GENERIC_CONFIRMATIONS:
        await message.answer(_NEUTRAL_REPLY)
        return

    # ── Price intent or bare area — calculate and upsell ─────────────────
    area = _parse_area(text)
    if _is_price_query(text) or area is not None:
        if area is not None:
            await _show_price_upsell(message, state, area)
        else:
            await message.answer(_PRICE_ASK_AREA_TEXT, reply_markup=_ai_keyboard())
        return

    # ── Typing indicator — shown while the LLM call runs ─────────────────
    if message.bot:
        await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    # ── Load conversation context ─────────────────────────────────────────
    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)

    # ── OpenAI reply ──────────────────────────────────────────────────────
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

    await message.answer(reply_text)

    # ── Persist exchange (non-fatal) ──────────────────────────────────────
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
    log.info(
        "ai_reply_sent",
        user_id=user_id,
        intent=intent,
        lead_temperature=lead_temperature,
        closing_confidence=closing_confidence,
    )


# ── Inline-button callbacks ───────────────────────────────────────────────────

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
