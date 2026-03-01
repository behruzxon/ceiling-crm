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

import json
import re
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from aiogram import F, Router
from aiogram.filters import StateFilter
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
from apps.bot.ui.cta import cta_intent_keyboard
from apps.bot.keyboards.pricing import design_keyboard
from apps.bot.states.pricing import PricingStates
from infrastructure.database.models.ai_conversation import AiConversationModel
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:ai_support")


# ── Explicit AI-mode FSM ──────────────────────────────────────────────────────

class AiSupportStates(StatesGroup):
    waiting_for_ai_question = State()


_EXIT_TEXTS: frozenset[str] = frozenset({"⬅️ Menyu"})


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

# ── Knowledge base (read once at import) ─────────────────────────────────────

_KB_PATH = Path(__file__).parents[4] / "shared" / "knowledge" / "uz.md"
_KNOWLEDGE_BASE: str = _KB_PATH.read_text(encoding="utf-8") if _KB_PATH.exists() else ""

# ── Static system prompt ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = f"""
Sen "Natijnoy Potolok" kompaniyasining tajribali savdo menejeri va botdagi yordamchisissan (ism: Zulfiya).
Kompaniya Qashqadaryo viloyatida stretch shiftlar o'rnatish bilan shug'ullanadi.

ASOSIY QOIDALAR:
- Faqat o'zbek tilida javob ber.
- Qisqa, ishonchli, samimiy javob ber (3–5 jumla). Keraksiz matn qo'shma.
- Faqat stretch shiftlar mavzusida gapir. Boshqa mavzularda: "Bu savolga javob bera olmayman, lekin shift haqida yordam bera olaman."
- Har doim suhbatni oldinga yuritmaga harakat qil — javobni savol bilan tugat.

SAVDO STRATEGIYASI (eng muhim):

1. NARX SO'RASA → avval xona o'lchamlarini so'ra, keyin aniq hisoblash ayt.
   Misol: "Xona o'lchamini bilsam, aniq narxni hisoblab beraman. Uzunlik va kenglik (masalan, 4×5 m)?"
   O'lcham olgach — narxni hisoblash va chegirmani eslatib ber.

2. IKKILANAYOTGANDA → bepul o'lchov taklifini qil (majburiyat yo'q, xavf yo'q).
   Misol: "Usta bepul kelib o'lchaydi — hech qanday majburiyat yo'q. Bugunmi yoki ertami qulay?"

3. HAR JAVOBDAN KEYIN → quyidagilardan birini so'ra (agar noma'lum bo'lsa):
   - Xona o'lchamlari (uzunlik × kenglik)
   - Xona turi (zal, yotoqxona, oshxona)
   - Joylashuv (tuman)
   - Dizayn qiziqishi

4. CHEGIRMA → o'lcham olgach avtomatik eslatib ber: 20 m²dan → 5%, 40 m²dan → 10%.

E'TIROZLARGA JAVOB (to'liq skript):

- "Qimmat" / "Arzonroq yo'qmi":
  → "Eng arzon variant — Odnotonniy (80 000 UZS/m²). 15 yillik kafolat va yashirin to'lov yo'qligi bilan narx oqlangan.
     O'lchamingizni aytsangiz, chegirma bilan aniq raqamni hisoblab beraman."

- "O'ylab ko'raman" / "Keyinroq":
  → "Albatta! Faqat bir taklif — usta bepul kelib o'lchaydi, narx hisoblanadi, majburiyat yo'q.
     Aniq raqamlar bilan o'ylash osonroq. Bugun vaqtingiz bormi?"

- "Boshqa kompaniya arzonroq":
  → "Raqobatchilar bilan taqqoslash uchun farqlarni ko'ring: 15 yillik kafolat, yashirin to'lov yo'q, mahalliy tez xizmat.
     Bepul o'lchamizdan foydalaning — keyin qaror qilasiz."

- "Vaqtim yo'q":
  → "O'lchov 30 daqiqa oladi. Qaysi vaqt qulay — ertalab yoki kechqurun?"

TAKRORLASHNI OLDINI OLISH:
- Suhbat tarixi mavjud bo'lsa (CONTEXT blokida ko'rsatilsa), "Assalomu alaykum" bilan boshlama.
- "Natijnoy Potolok" va "6 yildan beri" iboralarini faqat birinchi suhbatda yoki
  foydalanuvchi kompaniya haqida so'raganda ishlatib o'tish.
- CTA iborasini doim farqli qil — quyidagilardan navbatma-navbat tanlang:
    "O'lchamingizni ayting, hisoblaylik." |
    "Bepul o'lchovga yuboring — majburiyat yo'q." |
    "Katalogda yoqadigan dizayn bor — ochaymi?" |
    "Operatorimiz tez javob beradi — ulaymi?"
  Oxirgi CTA (CONTEXT blokida "Oxirgi CTA turi" sifatida ko'rsatiladi) qaysi bo'lsa,
  boshqa birini tanlang.

SHAXSIYLASHTIRISH (CONTEXT mavjud bo'lsa):
- interested_design → bir marta tabiiy tilga ol:
    "Siz avval [dizayn] ni ko'zda tutgandingiz — hali ham shu dizaynmidim?"
- last_dimensions → o'lchami o'zgarmadimi deb tasdiqlashni so'ra:
    "Xona o'lchami hali ham [o'lcham] m?"
- location → Qashqadaryo hududida xizmat borliqini tabiiy eslatib o'tish.

JAVOB FORMATI — faqat to'g'ri JSON, hech qanday qo'shimcha matn yo'q:
{{
  "intent": "price|catalog|operator|measurement|faq|objection|other",
  "reply": "...",
  "extracted": {{
    "interested_design": null,
    "last_dimensions": null,
    "location": null
  }}
}}

intent qiymatlari:
  price       — foydalanuvchi narx so'ramoqda
  catalog     — dizayn yoki katalog ko'rmoqchi
  operator    — operatorga murojaat qilmoqchi
  measurement — bepul o'lchov haqida so'ramoqda
  faq         — tez-tez so'raladigan savol (kafolat, o'rnatish muddati va h.k.)
  objection   — "qimmat" yoki narxga e'tiroz
  other       — boshqa

--- BILIMLAR BAZASI ---
{_KNOWLEDGE_BASE}
""".strip()

# Prompt for the cheap summary regeneration call
_SUMMARY_SYSTEM = (
    "Quyidagi suhbatni o'zbek tilida 2-4 jumlada qisqartir. "
    "Foydalanuvchining asosiy qiziqishi, so'ragan ma'lumotlari va "
    "muhim fikrlarini yozib qo'y. Faqat matn yoz, JSON shart emas."
)

# ── Dimension extraction ──────────────────────────────────────────────────────

# Pair: "5x4", "5*4", "5×4", "5.2x3.8", "5m x 4m", "5м 4м"
_PAIR_RE: re.Pattern[str] = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:m|м)?\s*[xX×*]\s*(\d+(?:[.,]\d+)?)\s*(?:m|м)?"
    r"|(?<!\d)(\d+(?:[.,]\d+)?)\s+(?:m|м)\s+(\d+(?:[.,]\d+)?)\s*(?:m|м)?(?!\d)",
    re.IGNORECASE,
)
# Bare number — whole message is just a number
_SINGLE_RE: re.Pattern[str] = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*$")


def _parse_dim(s: str) -> float | None:
    try:
        v = float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None
    return v if 0 < v <= 50 else None


def _extract_dims(text: str) -> tuple[float, float] | tuple[float, None] | None:
    """
    Returns:
      (length, width) — dimension pair found
      (length, None)  — single bare number in a very short message
      None            — no dimension detected
    """
    m = _PAIR_RE.search(text)
    if m:
        a = m.group(1) or m.group(3)
        b = m.group(2) or m.group(4)
        length, width = _parse_dim(a or ""), _parse_dim(b or "")
        if length and width:
            return length, width

    if len(text.strip()) <= 6:
        m2 = _SINGLE_RE.match(text)
        if m2:
            v = _parse_dim(m2.group(1))
            if v:
                return v, None

    return None


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
        f"{'Foydalanuvchi' if m['role'] == 'user' else 'Zulfiya'}: {m['text']}"
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


# ── Intent keyboards ──────────────────────────────────────────────────────────

_PRICE_BTN = InlineKeyboardButton(
    text="💰 Narxni hisoblash", callback_data="ai:start_price"
)
_CATALOG_BTN = InlineKeyboardButton(
    text="📂 Katalogga qarang", callback_data="ai:show_catalog"
)

_INTENT_KEYBOARDS: dict[str, InlineKeyboardMarkup | None] = {
    "price":       InlineKeyboardMarkup(inline_keyboard=[[_PRICE_BTN]]),
    "measurement": InlineKeyboardMarkup(inline_keyboard=[[_PRICE_BTN]]),
    "objection":   InlineKeyboardMarkup(inline_keyboard=[[_PRICE_BTN]]),
    "catalog":     InlineKeyboardMarkup(inline_keyboard=[[_CATALOG_BTN]]),
    "operator":    None,
    "faq":         InlineKeyboardMarkup(inline_keyboard=[[_PRICE_BTN], [_CATALOG_BTN]]),
    "other":       InlineKeyboardMarkup(inline_keyboard=[[_PRICE_BTN], [_CATALOG_BTN]]),
}

_FAILSAFE_TEXT = (
    "⚠️ Kechirasiz, texnik nosozlik yuz berdi.\n\n"
    "Operatorga murojaat qilishingiz yoki narxni hisoblashingiz mumkin:"
)
_FAILSAFE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [_PRICE_BTN],
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
    """Enter dedicated AI chat mode."""
    if message.from_user is None:
        await message.answer("Iltimos, botni shaxsiy chatda oching. 📩")
        return
    await state.clear()
    await state.set_state(AiSupportStates.waiting_for_ai_question)
    await message.answer(
        "🤖 <b>AI yordam</b>\n\nSavolingizni yozing:",
        reply_markup=_ai_keyboard(),
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
    text = message.text or ""
    user_id = message.from_user.id if message.from_user else 0

    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)

    try:
        result = await _call_ai(text, history, context_block)
        intent = str(result.get("intent", "other"))
        reply_text = str(result.get("reply", "")).strip()
        extracted: dict[str, Any] = result.get("extracted") or {}
        if not reply_text:
            raise ValueError("empty AI reply")
    except Exception:
        log.exception("ai_call_failed", user_id=user_id)
        await _store_user_message_only(
            user_id=user_id, user_text=text, current_messages=history
        )
        await message.answer(_FAILSAFE_TEXT, reply_markup=_ai_keyboard())
        return

    await message.answer(reply_text, reply_markup=_ai_keyboard())
    # Follow-up CTA: intent-based inline buttons (separate message — can't mix
    # ReplyKeyboard and InlineKeyboard in the same send call)
    await message.answer(
        "👇 Kerakli bo'limni tanlang:",
        reply_markup=cta_intent_keyboard(text),
    )

    await _persist_exchange(
        user_id=user_id,
        user_text=text,
        assistant_text=reply_text,
        intent=intent,
        extracted=extracted,
        current_profile=profile,
        current_messages=history,
        current_summary=summary,
    )
    log.info("ai_reply_sent", user_id=user_id, intent=intent, mode="explicit")


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

    # ── Dimension shortcut — skip AI, jump straight into pricing FSM ──────
    dims = _extract_dims(text)
    if dims is not None:
        length, width = dims
        if width is not None:
            area = round(length * width, 2)
            await state.set_state(PricingStates.choosing_design)
            await state.update_data(length=length, width=width, area=area)
            await message.answer(
                f"✅ O'lcham aniqlandi: <b>{length} × {width} m</b>  "
                f"|  Maydon: <b>{area:.2f} m²</b>\n\n"
                "Qaysi dizaynni tanlaysiz?",
                reply_markup=design_keyboard(),
            )
        else:
            await state.set_state(PricingStates.waiting_for_width)
            await state.update_data(length=length)
            await message.answer(
                f"✅ Uzunlik: <b>{length} m</b>\n\n"
                "Xona <b>kengligini</b> metrda kiriting:\n"
                "<i>Masalan: <code>3.8</code></i>",
            )
        return

    # ── Load conversation context ─────────────────────────────────────────
    profile, history, summary = await _load_context(user_id)
    context_block = _build_context_block(profile, summary)

    # ── OpenAI reply ──────────────────────────────────────────────────────
    try:
        result = await _call_ai(text, history, context_block)
        intent = str(result.get("intent", "other"))
        reply_text = str(result.get("reply", "")).strip()
        extracted: dict[str, Any] = result.get("extracted") or {}
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

    await message.answer(reply_text, reply_markup=cta_intent_keyboard(text))

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
    )
    log.info("ai_reply_sent", user_id=user_id, intent=intent)


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
