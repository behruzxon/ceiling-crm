"""
apps.bot.handlers.private.ai_scoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lead scoring (Redis-backed 0-100), objection detection, and objection
handling with negotiation-engine integration.

Cross-module dependencies (``ai_memory``) are lazy-imported to avoid
circular imports.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.handlers.private.ai_states import _ai_keyboard
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)


# ── Lead scoring (0-100, Redis-backed) ───────────────────────────────────────

async def _get_lead_score(user_id: int, *, bot_id: int | None = None) -> int:
    """Return current score from Redis, 0 if not set."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys
        raw = await get_redis().get(CacheKeys.ai_lead_score(user_id, bot_id=bot_id))
        return int(raw) if raw else 0
    except Exception:
        return 0


async def _add_lead_score(user_id: int, delta: int, *, bot_id: int | None = None) -> int:
    """Increment score by delta, clamp to [0, 100], persist 30-day TTL. Returns new score."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL
        current = await _get_lead_score(user_id, bot_id=bot_id)
        new_score = max(0, min(100, current + delta))
        await get_redis().set(
            CacheKeys.ai_lead_score(user_id, bot_id=bot_id), str(new_score), ttl=CacheTTL.AI_LEAD_SCORE
        )
        return new_score
    except Exception:
        return 0


def classify_score(score: int) -> str:
    """Map 0-100 numeric score to 'hot' | 'warm' | 'cold'."""
    if score >= 70:
        return "hot"
    if score >= 35:
        return "warm"
    return "cold"


# ── Objection detection ─────────────────────────────────────────────────────

_OBJECTION_EXPENSIVE_KW: frozenset[str] = frozenset({
    # Latin Uzbek
    "qimmat", "qimmatku", "qimmat ekan", "narx baland", "narxi baland",
    "qimmat bo'libdi", "qimmatmi", "qimmatroq",
    "qimmatga tushadi", "arzonroq bor", "arzon joy topaman",
    "boshqa kompaniyada arzon",
    # Latin Uzbek — financial constraints
    "pul yo'q", "pulim yo'q", "byudjetim yetmaydi", "byudjet kam",
    "pulim yetmaydi", "mablag' yetmaydi",
    # Russian
    "дорого", "дороговато", "цена высокая", "очень дорого",
    "дорогой", "слишком дорого",
    "нет денег", "денег нет",
    # Cyrillic Uzbek
    "қиммат", "нархи баланд", "пул йўқ",
})

_OBJECTION_TRUST_KW: frozenset[str] = frozenset({
    # Latin Uzbek
    "ishonch", "ishonmayman", "garantiya bormi", "kafolat bormi",
    "aldayapsiz", "firib", "ishonmiman", "ishonchim komil emas",
    "kafolat bormiga", "sifati qandayligini bilmiman", "tajriba bormi",
    # Russian
    "обман", "не верю", "гарантия", "надежно",
    "не доверяю", "не уверен",
    # Cyrillic Uzbek
    "ишонмайман", "кафолат борми", "ишонч", "алдаяпсиз",
})

_OBJECTION_COMPARE_KW: frozenset[str] = frozenset({
    # Latin Uzbek — price comparison / discount requests
    "boshqada arzon", "arzonroq", "narxni tushir", "skidka",
    "chegirma qil", "pasaytiring", "narxni pasaytir",
    # Russian
    "дешевле", "скидка", "снизьте цену", "скидку",
    # Cyrillic Uzbek
    "арзонроқ", "нархни тушир", "чегирма қил",
})

_OBJECTION_DELAY_KW: frozenset[str] = frozenset({
    # Latin Uzbek
    "keyinroq", "kechroq", "keyin qaytaman", "hozir emas",
    "vaqtim yo'q", "vaqt yo'q", "vaqt bo'lmaydi", "keyinga qoldiramiz",
    "o'ylab ko'raman", "fikrlab ko'raman",
    "erta", "indin", "boshqa payt",
    # Latin Uzbek — family/postpone
    "oilaga maslahat", "oiladan so'rab ko'raman", "oilam bilan maslahat",
    "uyga maslahat", "maslahat qilaman",
    "keyin yuboring", "keyinroq yuboring", "keyin jo'nating",
    # Russian
    "потом", "позже", "не сейчас", "я подумаю",
    "спрошу у семьи", "подумаю", "позже отправьте",
    # Cyrillic Uzbek
    "кейинроқ", "ҳозир эмас", "ўйлаб кўраман",
    "оилага маслаҳат", "кейин юборинг",
})

_OBJECTION_ANGRY_KW: frozenset[str] = frozenset({
    # Latin Uzbek
    "yomon", "kerakmas", "bezor", "zaybal", "nerv",
    "jonga tegdi", "aldov", "xafa", "tushunmadim",
    # Russian
    "плохо", "не надо", "достали", "бесит", "развод",
    # Cyrillic Uzbek
    "ёмон", "керакмас", "безор", "хафа", "алдов",
})

_OBJECTION_REPLIES: dict[str, str] = {
    "expensive": (
        "Narx balandroq ko'rinishi mumkin, lekin biz sifatli material va toza montaj qilamiz, "
        "15 yil kafolat bor. Natijnoy potolok uzoq xizmat qiladi — keyin qayta xarajat "
        "bo'lmaydi. Xohlasangiz, maydon (m²) va tumanni aytsangiz aniq hisoblab beraman 🙂"
    ),
    "trust": (
        "Tushunaman. Biz rasmiy ishlaymiz: sifatli material, toza montaj va 15 yil kafolat bor. "
        "Xohlasangiz, katalogimizdan real ishlarimizni ko'rsataman. "
        "Qaysi xonaga kerak va taxminiy maydon nechchi m²?"
    ),
    "compare": (
        "To'g'ri, bozorda turli narxlar bor. Bizda farq — sifat, montaj tozaligi va kafolat. "
        "Xohlasangiz, sizning maydon va tumanga qarab byudjet yoki premium variantni "
        "tavsiya qilaman 🙂 Maydon nechchi m²?"
    ),
    "delay": (
        "Mayli 🙂 Shoshilmasangiz ham bo'ladi. Men hozir sizga mos variantlarni tayyorlab "
        "qo'yaman, keyin tayyor bo'lsangiz davom ettiramiz. "
        "Qaysi xonaga kerak va taxminiy maydon nechchi m²?"
    ),
    "angry": (
        "Tushundim 🙂 Sizni bezovta qilmayman. Aniq yordam kerak bo'lsa yozing: "
        "narx hisoblab beraymi yoki katalog yuboraymi? Qaysi xonaga kerak?"
    ),
}

_OBJECTION_SCORE_DELTAS: dict[str, int] = {
    "expensive": 5,
    "trust":     5,
    "compare":   5,
    "delay":    -10,
    "angry":    -5,
}


def detect_objection(text: str) -> str | None:
    """Detect objection intent from user text.

    Returns 'expensive' | 'trust' | 'compare' | 'delay' | 'angry' | None.
    """
    lower = text.lower()
    if any(kw in lower for kw in _OBJECTION_EXPENSIVE_KW):
        return "expensive"
    if any(kw in lower for kw in _OBJECTION_TRUST_KW):
        return "trust"
    if any(kw in lower for kw in _OBJECTION_COMPARE_KW):
        return "compare"
    if any(kw in lower for kw in _OBJECTION_DELAY_KW):
        return "delay"
    if any(kw in lower for kw in _OBJECTION_ANGRY_KW):
        return "angry"
    return None


# Public alias
_detect_objection_type = detect_objection


def _build_objection_reply(kind: str, name: str | None = None) -> str:
    """Build a personalised objection reply string with CTA embedded."""
    reply = _OBJECTION_REPLIES.get(kind, "")
    if reply and name:
        reply = f"{name}, {reply[:1].lower()}{reply[1:]}"
    return reply


# ── Smart closing CTA ───────────────────────────────────────────────────────

async def _smart_closing_cta(state: FSMContext) -> str:
    """Return ONE targeted question based on what's still missing in the funnel."""
    fsm_data = await state.get_data()
    if not fsm_data.get("price_area"):
        return "Taxminan xonangiz nechchi m²? 🙂"
    if not fsm_data.get("price_district"):
        return "Qaysi tumandasiz? 📍"
    return "Telefon raqamingizni yuboring, mutaxassisimiz bog'lansin 📞"


# ── Objection handling ───────────────────────────────────────────────────────

async def _handle_objection(
    obj_type: str, message: Message, state: FSMContext, user_id: int
) -> None:
    """Send one canned objection reply (CTA already embedded in the text).

    Personalises with user name when known.  Deduplicates within 5 minutes.
    Saves objection type to memory for admin visibility.  Never raises.
    """
    if obj_type not in _OBJECTION_REPLIES:
        return

    # Lazy imports to avoid circular deps
    from apps.bot.handlers.private.ai_memory import _load_ai_memory, _save_ai_memory

    _bot_id = message.bot.id if message.bot else None

    # Resolve name + load memory for dedup check
    fsm_data = await state.get_data()
    name: str | None = fsm_data.get("user_name") or None
    _mem: dict[str, Any] = {}
    if user_id:
        _mem = await _load_ai_memory(user_id, bot_id=_bot_id)
        if not name:
            name = _mem.get("name") or None

        # Dedup: suppress identical reply within 5 minutes
        if (
            _mem.get("last_objection") == obj_type
            and _mem.get("last_objection_at")
            and int(time.time()) - int(_mem["last_objection_at"]) < 300
        ):
            delta = _OBJECTION_SCORE_DELTAS.get(obj_type, 0)
            if delta:
                asyncio.create_task(_add_lead_score(user_id, delta, bot_id=_bot_id))
            return

    # ── Negotiation engine: replace canned reply for price objections ──
    negotiation_result = None
    if obj_type in ("expensive", "compare") and user_id:
        try:
            from core.services.negotiation_engine_service import analyze_negotiation
            negotiation_result = analyze_negotiation(
                objection_type=obj_type,
                area_m2=_mem.get("area_m2"),
                design_type=_mem.get("design_type"),
                score=await _get_lead_score(user_id, bot_id=_bot_id),
                buyer_type=_mem.get("buyer_type"),
                closing_confidence=None,
                phone_captured=bool(_mem.get("phone_captured")),
                closing_attempted=bool(_mem.get("last_closing_attempt")),
                follow_up_count=0,
                previous_negotiation_tactic=_mem.get("last_negotiation_tactic"),
            )
        except Exception:
            pass  # fallback to canned reply

    if negotiation_result and negotiation_result.negotiation_detected and negotiation_result.reply:
        reply = negotiation_result.reply
        if name:
            reply = f"{name}, {reply[:1].lower()}{reply[1:]}"
    else:
        reply = _build_objection_reply(obj_type, name)

    await message.answer(reply, reply_markup=_ai_keyboard())

    delta = _OBJECTION_SCORE_DELTAS.get(obj_type, 0)
    if user_id:
        if delta:
            asyncio.create_task(_add_lead_score(user_id, delta, bot_id=_bot_id))
        # Persist objection type + negotiation state to memory
        _mem["last_objection"] = obj_type
        _mem["last_objection_at"] = int(time.time())
        if negotiation_result and negotiation_result.negotiation_detected:
            _mem["last_negotiation_tactic"] = negotiation_result.tactic
            _mem["last_negotiation_at"] = int(time.time())
            if negotiation_result.escalate_to_manager:
                _mem["negotiation_escalated"] = True
        asyncio.create_task(_save_ai_memory(user_id, _mem, bot_id=_bot_id))
        # Extend follow-up by 24h on delay objection
        if obj_type == "delay":
            asyncio.create_task(_extend_followup_on_delay(user_id))


async def _extend_followup_on_delay(user_id: int) -> None:
    """Extend next_follow_up_at by 24 h when user raises a delay objection. Never raises."""
    from datetime import timedelta, timezone
    try:
        factory = get_session_factory()
        async with factory() as session:
            from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
            repo = PostgresLeadRepository(session)
            leads = await repo.list_by_user(user_id, limit=1)
            if not leads:
                return
            lead = leads[0]
            if lead.next_follow_up_at is not None:
                from datetime import datetime as _dt
                new_fu = _dt.now(timezone.utc) + timedelta(hours=24)
                await repo.update_ai_scoring(lead.id, next_follow_up_at=new_fu)
                await session.commit()
                log.debug("followup_extended_delay_objection", lead_id=lead.id, user_id=user_id)
    except Exception:
        log.warning("extend_followup_on_delay_failed", user_id=user_id)
