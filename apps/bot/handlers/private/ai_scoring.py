"""
apps.bot.handlers.private.ai_scoring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Lead scoring (Redis-backed 0-100), objection detection (keyword + fuzzy),
severity scoring, and objection handling with negotiation-engine integration.

Cross-module dependencies (``ai_memory``) are lazy-imported to avoid
circular imports.
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import UTC
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.handlers.private.ai_states import _ai_keyboard
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)


# ── Objection severity ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ObjectionDetection:
    """Result of objection detection with severity."""
    objection_type: str          # expensive | trust | compare | delay | angry
    severity: str                # low | medium | high


# Severity amplifiers — if ANY of these appear alongside a base objection,
# bump severity up.  Checked against lowercased text.
_SEVERITY_HIGH_KW: frozenset[str] = frozenset({
    "umuman", "hech qachon", "aslo", "kerakmas", "olmayman",
    "rad etaman", "bo'lmaydi", "ortiqcha", "hech narsa",
    "juda qimmat", "juda baland", "слишком", "очень дорого",
    "никогда", "вообще", "ни за что", "жуда қиммат",
})

_SEVERITY_MEDIUM_KW: frozenset[str] = frozenset({
    "juda", "ancha", "biroz", "ko'p", "sal", "довольно",
    "жуда", "анча", "кўп",
})


# ── Lead scoring (0-100, Redis-backed) ───────────────────────────────────────

async def _get_lead_score(user_id: int) -> int:
    """Return current score from Redis, 0 if not set."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys
        raw = await get_redis().get(CacheKeys.ai_lead_score(user_id))
        return int(raw) if raw else 0
    except Exception:
        return 0


async def _add_lead_score(user_id: int, delta: int) -> int:
    """Increment score by delta, clamp to [0, 100], persist 30-day TTL. Returns new score."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL
        current = await _get_lead_score(user_id)
        new_score = max(0, min(100, current + delta))
        await get_redis().set(
            CacheKeys.ai_lead_score(user_id), str(new_score), ttl=CacheTTL.AI_LEAD_SCORE
        )
        return new_score
    except Exception:
        return 0


def classify_score(score: int) -> str:
    """Map 0-100 numeric score to 'hot' | 'warm' | 'cold'."""
    if score >= 60:
        return "hot"
    if score >= 30:
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

# ── Fuzzy patterns: regex-based variants that keyword matching misses ──────
# Each tuple: (compiled_regex, objection_type)
_FUZZY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # EXPENSIVE variants — misspellings & compound phrases
    (re.compile(r"qimmat\w*", re.I), "expensive"),              # qimmatda, qimmatroq, qimmatlik
    (re.compile(r"pul\w*\s+(yo.?q|yetma|kam)", re.I), "expensive"),  # pulim yetmayapti, pul yoq
    (re.compile(r"(hozir|menda?)\s+pul\s+yo.?q", re.I), "expensive"),  # hozir pul yo'q
    (re.compile(r"byudjet\w*\s+(yet|kam|oz)", re.I), "expensive"),  # byudjetim yetarli emas
    (re.compile(r"mablag.?\s+(yet|kam|oz)", re.I), "expensive"),   # mablag' yetmaydi
    (re.compile(r"narx\w*\s*(baland|yuqori|ko.?p|oshib)", re.I), "expensive"),
    # TRUST variants
    (re.compile(r"ishonch\w*\s+(komil|yo.?q|kam)", re.I), "trust"),  # ishonchim komil emas
    (re.compile(r"(kafolat|garantiya)\w*\s+(bor|ber|qan)", re.I), "trust"),
    (re.compile(r"sifat\w*\s+(qanday|yaxshi|yomon)", re.I), "trust"),
    (re.compile(r"aldab\w*|aldamay", re.I), "trust"),
    # COMPARE variants
    (re.compile(r"boshqa\w*\s+(joy|yer|kompaniya|firma)\w*\s+arzon", re.I), "compare"),
    (re.compile(r"(narx|pul)\w*\s+(tushir|pasayt|kamay)", re.I), "compare"),
    (re.compile(r"(skidka|chegirma)\w*\s+(bor|ber|qil)", re.I), "compare"),
    # DELAY variants
    (re.compile(r"keyin\w*\s+(yoz|qo.?ng|gaplash|qayt)", re.I), "delay"),  # keyinroq yozaman
    (re.compile(r"(vaqt|fursat)\w*\s+(yo.?q|bo.?lma|kam)", re.I), "delay"),
    (re.compile(r"(oila|uy)\w*\s*(bilan\s+)?maslahat", re.I), "delay"),
    (re.compile(r"o.?ylab\s+ko.?r", re.I), "delay"),  # o'ylab ko'raman
    (re.compile(r"fikrlab\s+ko.?r", re.I), "delay"),
    # ANGRY variants
    (re.compile(r"(jonga?|asab)\s+teg", re.I), "angry"),
    (re.compile(r"bezor\s+qil", re.I), "angry"),
]

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


def _score_severity(text: str) -> str:
    """Score objection severity: 'low' | 'medium' | 'high'."""
    lower = text.lower()
    if any(kw in lower for kw in _SEVERITY_HIGH_KW):
        return "high"
    if any(kw in lower for kw in _SEVERITY_MEDIUM_KW):
        return "medium"
    return "low"


def detect_objection(text: str) -> str | None:
    """Detect objection intent from user text (backward-compatible).

    Returns 'expensive' | 'trust' | 'compare' | 'delay' | 'angry' | None.
    """
    result = detect_objection_full(text)
    return result.objection_type if result else None


def detect_objection_full(text: str) -> ObjectionDetection | None:
    """Detect objection intent with severity scoring.

    Uses two-pass detection:
      1. Exact keyword matching (fast, 130+ keywords)
      2. Fuzzy regex matching (catches misspellings/variants)

    Returns ObjectionDetection(type, severity) or None.
    """
    lower = text.lower()

    # ── Pass 1: Exact keyword match (existing, fast) ─────────────────
    obj_type: str | None = None
    if any(kw in lower for kw in _OBJECTION_EXPENSIVE_KW):
        obj_type = "expensive"
    elif any(kw in lower for kw in _OBJECTION_TRUST_KW):
        obj_type = "trust"
    elif any(kw in lower for kw in _OBJECTION_COMPARE_KW):
        obj_type = "compare"
    elif any(kw in lower for kw in _OBJECTION_DELAY_KW):
        obj_type = "delay"
    elif any(kw in lower for kw in _OBJECTION_ANGRY_KW):
        obj_type = "angry"

    # ── Pass 2: Fuzzy regex match (catches variants) ─────────────────
    if obj_type is None:
        for pattern, fuzzy_type in _FUZZY_PATTERNS:
            if pattern.search(lower):
                obj_type = fuzzy_type
                break

    if obj_type is None:
        return None

    severity = _score_severity(text)
    return ObjectionDetection(objection_type=obj_type, severity=severity)


# Public alias (backward compat)
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
    obj_type: str, message: Message, state: FSMContext, user_id: int,
    severity: str = "low",
) -> None:
    """Send objection reply with negotiation engine + AI-generated alternatives.

    Personalises with user name when known.  Deduplicates within 5 minutes.
    Saves objection type + severity to memory for admin visibility.  Never raises.
    """
    if obj_type not in _OBJECTION_REPLIES:
        return

    # Lazy imports to avoid circular deps
    from apps.bot.handlers.private.ai_memory import _load_ai_memory, _save_ai_memory

    # Resolve name + load memory for dedup check
    fsm_data = await state.get_data()
    name: str | None = fsm_data.get("user_name") or None
    _mem: dict[str, Any] = {}
    if user_id:
        _mem = await _load_ai_memory(user_id)
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
                asyncio.create_task(_add_lead_score(user_id, delta))
            return

    score = await _get_lead_score(user_id) if user_id else 0

    # ── Negotiation engine: all objection types now supported ──────────
    negotiation_result = None
    if user_id:
        try:
            from core.services.negotiation_engine_service import analyze_negotiation

            # Load adaptive weights from Redis (outcome-based learning)
            _neg_weights: dict[str, float] | None = None
            try:
                import json as _json

                from infrastructure.cache.client import get_redis as _get_redis
                from infrastructure.cache.keys import CacheKeys as _CK
                _raw_w = await _get_redis().get(_CK.adaptive_weights("negotiation"))
                if _raw_w:
                    _neg_weights = _json.loads(_raw_w)
            except Exception:
                pass

            negotiation_result = analyze_negotiation(
                objection_type=obj_type,
                severity=severity,
                area_m2=_mem.get("area_m2"),
                design_type=_mem.get("design_type"),
                score=score,
                buyer_type=_mem.get("buyer_type"),
                closing_confidence=None,
                phone_captured=bool(_mem.get("phone_captured")),
                closing_attempted=bool(_mem.get("last_closing_attempt")),
                follow_up_count=0,
                previous_negotiation_tactic=_mem.get("last_negotiation_tactic"),
                tactic_weights=_neg_weights,
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

    # ── Adjust score delta by severity ─────────────────────────────────
    base_delta = _OBJECTION_SCORE_DELTAS.get(obj_type, 0)
    if severity == "high":
        delta = base_delta * 2 if base_delta < 0 else base_delta  # double penalty for high
    elif severity == "medium":
        delta = int(base_delta * 1.5) if base_delta < 0 else base_delta
    else:
        delta = base_delta

    if user_id:
        if delta:
            asyncio.create_task(_add_lead_score(user_id, delta))
        # Persist objection type + severity + negotiation state to memory
        _mem["last_objection"] = obj_type
        _mem["last_objection_severity"] = severity
        _mem["last_objection_at"] = int(time.time())
        if negotiation_result and negotiation_result.negotiation_detected:
            _mem["last_negotiation_tactic"] = negotiation_result.tactic
            _mem["last_negotiation_at"] = int(time.time())
            if negotiation_result.escalate_to_manager:
                _mem["negotiation_escalated"] = True
        asyncio.create_task(_save_ai_memory(user_id, _mem))

        # Log tactic outcome for outcome-based learning
        tactic_for_log = (
            negotiation_result.tactic
            if negotiation_result and negotiation_result.negotiation_detected
            else f"objection_{obj_type}"
        )
        from core.services.tactic_outcome_logger import log_tactic_outcome
        asyncio.create_task(log_tactic_outcome(
            event_type="negotiation",
            tactic_name=tactic_for_log,
            user_id=user_id,
            objection_type=obj_type,
            lead_score_at_time=score,
            lead_temperature_at_time=classify_score(score),
        ))

        # Contextual delay handling
        if obj_type == "delay":
            asyncio.create_task(
                _extend_followup_on_delay(user_id, severity, score)
            )

        # Real-time admin alert for first objection from HOT lead
        is_hot = score >= 60 or classify_score(score) == "hot"
        is_first = _mem.get("last_objection") is None or _mem.get("last_objection") != obj_type
        if is_hot and is_first:
            tactic_name = (
                negotiation_result.tactic if negotiation_result and negotiation_result.negotiation_detected
                else "none"
            )
            asyncio.create_task(
                _alert_hot_lead_objection(
                    user_id=user_id,
                    obj_type=obj_type,
                    severity=severity,
                    user_message=message.text or "",
                    tactic=tactic_name,
                    score=score,
                )
            )


async def _extend_followup_on_delay(
    user_id: int, severity: str = "low", score: int = 0,
) -> None:
    """Extend follow-up contextually based on lead temperature and severity.

    HOT lead + low severity  → +6h  (softer but faster re-engagement)
    HOT lead + high severity → +12h (give space, but don't lose)
    WARM lead                → +24h (standard)
    COLD lead                → +48h (lower pressure)
    """
    from datetime import timedelta
    try:
        classification = classify_score(score)

        if classification == "hot":
            hours = 6 if severity == "low" else 12
        elif classification == "warm":
            hours = 24
        else:  # cold
            hours = 48

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
                new_fu = _dt.now(UTC) + timedelta(hours=hours)
                await repo.update_ai_scoring(lead.id, next_follow_up_at=new_fu)
                await session.commit()
                log.debug(
                    "followup_extended_delay_objection",
                    lead_id=lead.id, user_id=user_id,
                    hours=hours, severity=severity,
                    classification=classification,
                )
    except Exception:
        log.warning("extend_followup_on_delay_failed", user_id=user_id)


async def _alert_hot_lead_objection(
    *,
    user_id: int,
    obj_type: str,
    severity: str,
    user_message: str,
    tactic: str,
    score: int,
) -> None:
    """Send real-time alert to admin group for HOT lead's first objection.

    Deduped via Redis: one alert per user per 2 hours.
    """
    try:
        from infrastructure.cache.client import get_redis
        from shared.config import get_settings

        redis = get_redis()
        dedup_key = f"hot_obj_alert:{user_id}"

        # Dedup: one alert per user per 2 hours
        was_set = await redis.set(dedup_key, "1", ttl=7200, nx=True)
        if not was_set:
            return

        settings = get_settings()
        admin_group_id = settings.bot.admin_group_id

        from core.services.negotiation_engine_service import TACTIC_LABELS
        tactic_label = TACTIC_LABELS.get(tactic, tactic)

        _SEV_BADGES = {"low": "\U0001f7e2", "medium": "\U0001f7e1", "high": "\U0001f534"}
        _TYPE_LABELS = {
            "expensive": "PRICE", "trust": "TRUST", "compare": "COMPARE",
            "delay": "DELAY", "angry": "ANGRY",
        }

        sev_badge = _SEV_BADGES.get(severity, "\u26aa")
        type_label = _TYPE_LABELS.get(obj_type, obj_type.upper())
        msg_preview = user_message[:200] if user_message else "\u2014"

        # Find lead ID for reference
        lead_ref = ""
        try:
            factory = get_session_factory()
            async with factory() as session:
                from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
                leads = await PostgresLeadRepository(session).list_by_user(user_id, limit=1)
                if leads:
                    lead_ref = f"\n\U0001f4cb Lead: #{leads[0].id}"
        except Exception:
            pass

        text = (
            f"\U0001f525 <b>HOT Lead Objection</b>\n"
            f"{lead_ref}\n"
            f"\U0001f3af Score: {score}/100\n"
            f"\U0001f6ab Type: <b>{type_label}</b>\n"
            f"{sev_badge} Severity: <b>{severity.upper()}</b>\n"
            f'\U0001f4ac Message: "{msg_preview}"\n\n'
            f"<b>Suggested tactic:</b>\n{tactic_label}"
        )

        from aiogram import Bot
        bot: Bot | None = None
        try:
            bot = Bot(token=settings.bot.token.get_secret_value())
            await bot.send_message(
                chat_id=admin_group_id, text=text, parse_mode="HTML",
            )
        finally:
            if bot:
                await bot.session.close()

    except Exception:
        log.warning("hot_lead_objection_alert_failed", user_id=user_id)
