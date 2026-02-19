"""
AI-powered free-text handler for private DM chats.

Pipeline
--------
  Incoming text (no active FSM state)
    ├─ Dimension pair found (e.g. "5x4", "5м 4м") → jump to pricing FSM at design step
    ├─ Single bare number (e.g. "5")               → start pricing FSM at width step
    └─ General question                            → OpenAI JSON reply + intent keyboard

OpenAI response schema
  {"intent": "price|catalog|operator|measurement|faq|objection|other",
   "reply": "<Uzbek reply text>"}

Intent keyboards
  price / measurement / objection → "💰 Narxni hisoblash" button
  catalog                         → "📂 Katalogga qarang" button
  operator                        → no keyboard (phone numbers in knowledge base)
  faq / other                     → both buttons

Memory: ai_user_memory table updated non-fatally after every reply.
Failsafe: static message if OpenAI is unavailable.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import sqlalchemy as sa
from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from openai import AsyncOpenAI

from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.pricing import design_keyboard
from apps.bot.states.pricing import PricingStates
from infrastructure.database.models.ai_memory import AiMemoryModel
from infrastructure.database.session import get_session_factory
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:ai_support")

# ── Knowledge base (read once at import time) ──────────────────────────────

_KB_PATH = Path(__file__).parents[4] / "shared" / "knowledge" / "uz.md"
_KNOWLEDGE_BASE: str = _KB_PATH.read_text(encoding="utf-8") if _KB_PATH.exists() else ""

# ── System prompt ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = f"""
Sen "Natijnoy Potolok" kompaniyasining do'stona savdo yordamchisissan (ism: Zulfiya).
Kompaniya Qashqadaryo viloyatida gipyum shiftlar o'rnatish bilan shug'ullanadi.

Qoidalar:
- Faqat o'zbek tilida javob ber.
- Qisqa, samimiy va aniq javob ber (3-4 jumladan oshirma).
- Faqat stretch shiftlar mavzusida gapir. Boshqa mavzularda: "Bu savolga javob bera olmayman."
- Xona o'lchami (uzunlik × kenglik) tilga olinsa, narx kalkulyatorini taklif qil.
- Javob FAQAT quyidagi JSON formatida bo'lsin:
  {{"intent": "price|catalog|operator|measurement|faq|objection|other", "reply": "..."}}

intent qiymatlari:
  price       — foydalanuvchi narx so'ramoqda
  catalog     — dizayn yoki katalog ko'rmoqchi
  operator    — operatorga murojaat qilmoqchi
  measurement — bepul o'lchov haqida so'ramoqda
  faq         — tez-tez so'raladigan savol (kafolat, muddati va h.k.)
  objection   — "qimmat" yoki shikoyat
  other       — boshqa

--- BILIMLAR BAZASI ---
{_KNOWLEDGE_BASE}
""".strip()

# ── Dimension extraction ────────────────────────────────────────────────────

# Pair: "5x4", "5*4", "5×4", "5.2x3.8", "5m x 4m", "5м 4м"
_PAIR_RE: re.Pattern[str] = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:m|м)?\s*[xX×*]\s*(\d+(?:[.,]\d+)?)\s*(?:m|м)?"
    r"|(?<!\d)(\d+(?:[.,]\d+)?)\s+(?:m|м)\s+(\d+(?:[.,]\d+)?)\s*(?:m|м)?(?!\d)",
    re.IGNORECASE,
)
# Single bare number (whole message is just a number)
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
      (length, width) — pair found
      (length, None)  — single bare number
      None            — no dimension found
    """
    m = _PAIR_RE.search(text)
    if m:
        a = m.group(1) or m.group(3)
        b = m.group(2) or m.group(4)
        length, width = _parse_dim(a or ""), _parse_dim(b or "")
        if length and width:
            return length, width

    # Single extraction only for very short messages (bare number)
    if len(text.strip()) <= 6:
        m2 = _SINGLE_RE.match(text)
        if m2:
            v = _parse_dim(m2.group(1))
            if v:
                return v, None

    return None


# ── OpenAI client (lazy singleton) ──────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        # AI_API_KEY overrides OPENAI_API_KEY when set
        if settings.ai.api_key:
            api_key = settings.ai.api_key.get_secret_value()
        else:
            api_key = settings.openai.api_key.get_secret_value()
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


async def _call_ai(user_text: str) -> dict[str, str]:
    """Call OpenAI and return parsed JSON {"intent": ..., "reply": ...}."""
    settings = get_settings()
    client = _get_client()
    resp = await client.chat.completions.create(
        model=settings.ai.model,
        temperature=0.3,
        max_tokens=512,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


# ── Memory (non-fatal) ──────────────────────────────────────────────────────

async def _update_memory(user_id: int, intent: str, snippet: str) -> None:
    """Upsert ai_user_memory. Swallows all exceptions to keep the main flow safe."""
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        factory = get_session_factory()
        async with factory() as session:
            profile = {"last_intent": intent, "last_msg": snippet}
            stmt = (
                pg_insert(AiMemoryModel)
                .values(user_id=user_id, profile=profile)
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "profile": profile,
                        "updated_at": sa.func.now(),
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()
    except Exception:
        log.warning("ai_memory_update_failed", user_id=user_id)


# ── Intent keyboards ────────────────────────────────────────────────────────

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


# ── Main handler ─────────────────────────────────────────────────────────────

@router.message(
    F.chat.type == "private",
    F.text,
    StateFilter(default_state),
)
async def handle_ai_message(message: Message, state: FSMContext, **data: object) -> None:
    """Route free-text DMs: dimension shortcut or AI reply."""
    text = message.text or ""
    user_id = message.from_user.id if message.from_user else 0

    # ── Dimension shortcut — bypass AI call ───────────────────────────────
    dims = _extract_dims(text)
    if dims is not None:
        length, width = dims
        if width is not None:
            # Both dimensions known — jump straight to design selection
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
            # One dimension — start pricing and wait for width
            await state.set_state(PricingStates.waiting_for_width)
            await state.update_data(length=length)
            await message.answer(
                f"✅ Uzunlik: <b>{length} m</b>\n\n"
                "Xona <b>kengligini</b> metrda kiriting:\n"
                "<i>Masalan: <code>3.8</code></i>",
            )
        return

    # ── OpenAI reply ──────────────────────────────────────────────────────
    try:
        result = await _call_ai(text)
        intent = str(result.get("intent", "other"))
        reply_text = str(result.get("reply", "")).strip()
        if not reply_text:
            raise ValueError("empty AI reply")
    except Exception:
        log.exception("ai_call_failed", user_id=user_id)
        await message.answer(_FAILSAFE_TEXT, reply_markup=_FAILSAFE_KB)
        return

    keyboard = _INTENT_KEYBOARDS.get(intent)
    await message.answer(reply_text, reply_markup=keyboard)

    # Non-fatal memory update (fire-and-forget style)
    await _update_memory(user_id, intent, text[:120])
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
