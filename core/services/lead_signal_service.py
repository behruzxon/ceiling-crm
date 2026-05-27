"""
core.services.lead_signal_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic free-text signal extraction for lead scoring 2.0.

Extracts customer intent, objection type, urgency level, area and budget
mentions from Uzbek/Russian text using keyword rules.  No AI — pure
pattern matching.
"""

from __future__ import annotations

import re
from typing import Any

from core.schemas.lead_signal import LeadSignalResult
from shared.constants.enums import CustomerIntent, ObjectionType, UrgencyLevel
from shared.utils.area_parser import parse_area

# ── Stop keywords (checked first, multi-word before single-word) ──────────────

_STOP_KEYWORDS: tuple[str, ...] = (
    "kerak emas",
    "kerakmas",
    "yozmang",
    "qiziqmayman",
    "stop",
    "bekor",
    "не надо",
    "стоп",
    "отмена",
    "отстаньте",
)

# ── Intent keyword groups ─────────────────────────────────────────────────────

_ORDER_STRONG: tuple[str, ...] = (
    "zakaz",
    "buyurtma",
    "заказать",
    "заказ",
)

_ORDER_WEAK: tuple[str, ...] = (
    "boshlaymiz",
    "chaqirish",
    "kelish",
    "qilamiz",
    "kerak",
)

_OPERATOR_KEYWORDS: tuple[str, ...] = (
    "odam bilan",
    "operator",
    "telefon qiling",
    "bog'laning",
    "оператор",
    "позвоните",
    "свяжитесь",
    "pozvonite",
)

_MEASUREMENT_KEYWORDS: tuple[str, ...] = (
    "usta",
    "o'lchovchi",
    "o'lchov",
    "olchov",
    "замер",
    "мастер",
)

_PRICE_KEYWORDS: tuple[str, ...] = (
    "narx",
    "qancha",
    "nech pul",
    "nechpul",
    "hisobla",
    "kvadrat",
    "m2",
    "kv",
    "цена",
    "сколько",
    "стоимость",
    "почем",
    "skolko",
    "stoit",
)

_CATALOG_KEYWORDS: tuple[str, ...] = (
    "katalog",
    "model",
    "rasm",
    "gulli",
    "matoviy",
    "dizayn",
    "rang",
    "каталог",
    "фото",
    "модел",
)

_DISCOUNT_KEYWORDS: tuple[str, ...] = (
    "chegirma",
    "arzonroq",
    "tushirib berasizmi",
    "skidka",
    "скидка",
    "дешевле",
)

_INSTALLATION_TIME_KEYWORDS: tuple[str, ...] = (
    "qachon o'rnatiladi",
    "qancha vaqt",
    "o'rnatish muddati",
    "когда установка",
    "сроки установки",
)

_LOCATION_SERVICE_KEYWORDS: tuple[str, ...] = (
    "kelib bering",
    "manzil",
    "lokatsiya",
    "адрес",
    "приедете к нам",
)

# ── Objection keyword groups ─────────────────────────────────────────────────

_PRICE_OBJECTION: tuple[str, ...] = (
    "qimmat",
    "qimmatku",
    "pulim yetmaydi",
    "дорого",
    "дороговато",
    "dorogo",
)

_TIME_OBJECTION: tuple[str, ...] = (
    "uzoq davom",
    "qachon tugaydi",
    "ko'p vaqt",
    "vaqt yo'q",
    "долго",
    "нет времени",
)

_TRUST_OBJECTION: tuple[str, ...] = (
    "ishonch",
    "kafolat",
    "oldin ishlaringiz",
    "real rasm",
    "mijozlar fikri",
    "гарантия",
    "отзывы",
    "реальные фото",
)

_CONSULTATION_OBJECTION: tuple[str, ...] = (
    "maslahat kerak",
    "so'rab ko'raman",
    "o'ylab ko'raman",
    "посоветуюсь",
    "подумаю",
)

_COMPARING_OBJECTION: tuple[str, ...] = (
    "boshqa firma",
    "raqobat",
    "taqqosla",
    "boshqa joy",
    "другая фирма",
    "сравнить",
    "конкурент",
)

_NOT_READY_OBJECTION: tuple[str, ...] = (
    "keyinroq",
    "hali emas",
    "hozir emas",
    "позже",
    "не сейчас",
    "потом",
)

_LOCATION_OBJECTION: tuple[str, ...] = (
    "uzoq joy",
    "kelasizlarmi",
    "bizning tumanga",
    "далеко",
)

_FAMILY_OBJECTION: tuple[str, ...] = (
    "erim bilan",
    "xotinim bilan",
    "oilaga",
    "ota-onam",
    "с мужем",
    "с женой",
    "с семьей",
)

# ── Urgency keyword groups ────────────────────────────────────────────────────

_HIGH_URGENCY: tuple[str, ...] = (
    "bugun",
    "ertaga",
    "tez",
    "hozir",
    "shoshilinch",
    "shu hafta",
    "сегодня",
    "завтра",
    "срочно",
    "сейчас",
)

_MEDIUM_URGENCY: tuple[str, ...] = (
    "shu oyda",
    "yaqinda",
    "tezroq",
    "на этой неделе",
    "в этом месяце",
    "скоро",
)

# ── Budget pattern ────────────────────────────────────────────────────────────

_BUDGET_RE: re.Pattern[str] = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:mln|million|миллион|млн|ming|тыс|минг)",
    re.IGNORECASE,
)

_BUDGET_MILLION_UNITS: tuple[str, ...] = ("mln", "million", "миллион", "млн")
_BUDGET_THOUSAND_UNITS: tuple[str, ...] = ("ming", "тыс", "минг")

# ── Language detection ────────────────────────────────────────────────────────

_CYRILLIC_RE: re.Pattern[str] = re.compile(r"[а-яА-ЯёЁ]")

# ── Score deltas per intent ───────────────────────────────────────────────────

_INTENT_DELTAS: dict[CustomerIntent, int] = {
    CustomerIntent.WANTS_PRICE: 15,
    CustomerIntent.WANTS_CATALOG: 10,
    CustomerIntent.WANTS_ORDER: 30,
    CustomerIntent.WANTS_OPERATOR: 25,
    CustomerIntent.WANTS_MEASUREMENT: 25,
    CustomerIntent.WANTS_DISCOUNT: 10,
    CustomerIntent.WANTS_INSTALLATION_TIME: 5,
    CustomerIntent.WANTS_LOCATION_SERVICE: 5,
    CustomerIntent.SENDS_OBJECTION: 5,
}


class LeadSignalService:
    """Deterministic signal extraction from free-text messages."""

    @staticmethod
    def extract_signals(
        text: str,
        language_hint: str | None = None,
    ) -> LeadSignalResult:
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )

        norm = TextNormalizationService.normalize(text)
        search_text = norm.latin
        t = search_text.lower().strip()
        original_lower = text.lower().strip()
        lang = language_hint or ("ru" if "russian" in norm.detected_languages else "uz")

        intent = LeadSignalService.detect_intent(search_text)
        if intent == CustomerIntent.UNCLEAR:
            intent = LeadSignalService.detect_intent(text)

        objection = LeadSignalService.detect_objection(search_text)
        if objection is None:
            objection = LeadSignalService.detect_objection(text)

        urgency = LeadSignalService.detect_urgency(search_text)
        if urgency == UrgencyLevel.LOW:
            urgency = LeadSignalService.detect_urgency(text)

        area = LeadSignalService.detect_area_mention(search_text)
        if area is None:
            area = LeadSignalService.detect_area_mention(text)

        budget = LeadSignalService.detect_budget_mention(text)
        keywords = LeadSignalService._collect_keywords(t)
        keywords.extend(
            kw for kw in LeadSignalService._collect_keywords(original_lower) if kw not in keywords
        )

        if objection is not None and intent == CustomerIntent.UNCLEAR:
            intent = CustomerIntent.SENDS_OBJECTION

        delta = LeadSignalService._compute_score_delta(
            intent,
            objection,
            urgency,
            area,
            budget,
        )
        confidence = LeadSignalService._compute_confidence(
            intent,
            objection,
            urgency,
            area,
            budget,
            keywords,
        )

        should_disable = intent == CustomerIntent.STOP_REQUEST
        should_notify = (
            intent in (CustomerIntent.WANTS_ORDER, CustomerIntent.WANTS_OPERATOR)
            or urgency == UrgencyLevel.HIGH
        )

        return LeadSignalResult(
            intent=intent.value,
            objection_type=objection.value if objection else None,
            urgency=urgency.value,
            area_m2=area,
            budget_amount=budget,
            lead_score_delta=delta,
            confidence_score=confidence,
            detected_keywords=keywords,
            language=lang,
            should_disable_followup=should_disable,
            should_notify_admin=should_notify,
        )

    @staticmethod
    def detect_intent(text: str) -> CustomerIntent:
        t = text.lower().strip()

        for kw in _STOP_KEYWORDS:
            if kw in t:
                return CustomerIntent.STOP_REQUEST

        for kw in _ORDER_STRONG:
            if kw in t:
                return CustomerIntent.WANTS_ORDER

        for kw in _OPERATOR_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_OPERATOR

        for kw in _MEASUREMENT_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_MEASUREMENT

        for kw in _PRICE_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_PRICE

        for kw in _CATALOG_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_CATALOG

        for kw in _DISCOUNT_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_DISCOUNT

        for kw in _INSTALLATION_TIME_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_INSTALLATION_TIME

        for kw in _LOCATION_SERVICE_KEYWORDS:
            if kw in t:
                return CustomerIntent.WANTS_LOCATION_SERVICE

        for kw in _ORDER_WEAK:
            if kw in t:
                return CustomerIntent.WANTS_ORDER

        # Fuzzy fallback for strong keywords (typos/transliteration misses)
        fuzzy = LeadSignalService._fuzzy_intent(t)
        if fuzzy is not None:
            return fuzzy

        return CustomerIntent.UNCLEAR

    @staticmethod
    def detect_objection(text: str) -> ObjectionType | None:
        t = text.lower().strip()

        for kw in _PRICE_OBJECTION:
            if kw in t:
                return ObjectionType.PRICE

        for kw in _TRUST_OBJECTION:
            if kw in t:
                return ObjectionType.TRUST

        for kw in _FAMILY_OBJECTION:
            if kw in t:
                return ObjectionType.SPOUSE_FAMILY_DECISION

        for kw in _NOT_READY_OBJECTION:
            if kw in t:
                return ObjectionType.NOT_READY

        for kw in _COMPARING_OBJECTION:
            if kw in t:
                return ObjectionType.COMPARING

        for kw in _CONSULTATION_OBJECTION:
            if kw in t:
                return ObjectionType.NEED_CONSULTATION

        for kw in _TIME_OBJECTION:
            if kw in t:
                return ObjectionType.TIME

        for kw in _LOCATION_OBJECTION:
            if kw in t:
                return ObjectionType.LOCATION

        fuzzy = LeadSignalService._fuzzy_objection(t)
        if fuzzy is not None:
            return fuzzy

        return None

    @staticmethod
    def detect_urgency(text: str) -> UrgencyLevel:
        t = text.lower().strip()

        for kw in _HIGH_URGENCY:
            if kw in t:
                return UrgencyLevel.HIGH

        for kw in _MEDIUM_URGENCY:
            if kw in t:
                return UrgencyLevel.MEDIUM

        return UrgencyLevel.LOW

    @staticmethod
    def detect_area_mention(text: str) -> float | None:
        return parse_area(text)

    @staticmethod
    def detect_budget_mention(text: str) -> int | None:
        m = _BUDGET_RE.search(text)
        if not m:
            return None
        raw = m.group(1).replace(",", ".")
        try:
            val = float(raw)
        except ValueError:
            return None
        unit_text = text[m.end(1) : m.end()].lower().strip()
        if any(u in unit_text for u in _BUDGET_MILLION_UNITS):
            return int(val * 1_000_000)
        if any(u in unit_text for u in _BUDGET_THOUSAND_UNITS):
            return int(val * 1_000)
        return int(val)

    @staticmethod
    def calculate_lead_score(
        memory: dict[str, Any],
        recent_events: list[dict[str, Any]],
        signal: LeadSignalResult,
    ) -> int:
        if signal.intent == CustomerIntent.STOP_REQUEST.value:
            return 0

        base = memory.get("lead_score", 0)

        event_scores: dict[str, int] = {
            "opened_catalog": 10,
            "used_price_calculator": 20,
            "price_calculated": 20,
            "phone_shared": 40,
            "operator_requested": 35,
            "image_sent": 25,
            "clicked_order": 30,
        }
        seen: set[str] = set()
        for ev in recent_events:
            et = ev.get("event_type", "")
            if et not in seen:
                seen.add(et)
                base += event_scores.get(et, 0)

        base += signal.lead_score_delta
        return max(0, min(base, 100))

    @staticmethod
    def classify_temperature(score: int) -> str:
        if score >= 70:
            return "hot"
        if score >= 31:
            return "warm"
        return "cold"

    @staticmethod
    def update_memory_from_signal(
        memory_data: dict[str, Any],
        signal: LeadSignalResult,
    ) -> dict[str, Any]:
        updated = dict(memory_data)
        updated["last_intent"] = signal.intent
        if signal.objection_type:
            updated["objection_type"] = signal.objection_type
        updated["urgency"] = signal.urgency
        updated["lead_score_delta"] = signal.lead_score_delta
        updated["signal_confidence"] = signal.confidence_score
        updated["last_signal_language"] = signal.language
        if signal.area_m2 is not None:
            updated["area_m2"] = signal.area_m2
        if signal.budget_amount is not None:
            updated["budget_amount"] = signal.budget_amount
        if signal.should_disable_followup:
            updated["should_disable_followup"] = True
        return updated

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _collect_keywords(t: str) -> list[str]:
        found: list[str] = []
        all_kw_groups = (
            _STOP_KEYWORDS,
            _ORDER_STRONG,
            _ORDER_WEAK,
            _OPERATOR_KEYWORDS,
            _MEASUREMENT_KEYWORDS,
            _PRICE_KEYWORDS,
            _CATALOG_KEYWORDS,
            _DISCOUNT_KEYWORDS,
            _INSTALLATION_TIME_KEYWORDS,
            _LOCATION_SERVICE_KEYWORDS,
            _PRICE_OBJECTION,
            _TIME_OBJECTION,
            _TRUST_OBJECTION,
            _CONSULTATION_OBJECTION,
            _COMPARING_OBJECTION,
            _NOT_READY_OBJECTION,
            _LOCATION_OBJECTION,
            _FAMILY_OBJECTION,
            _HIGH_URGENCY,
            _MEDIUM_URGENCY,
        )
        for group in all_kw_groups:
            for kw in group:
                if kw in t:
                    found.append(kw)
        return found

    @staticmethod
    def _compute_score_delta(
        intent: CustomerIntent,
        objection: ObjectionType | None,
        urgency: UrgencyLevel,
        area: float | None,
        budget: int | None,
    ) -> int:
        if intent == CustomerIntent.STOP_REQUEST:
            return 0

        delta = _INTENT_DELTAS.get(intent, 0)
        if area is not None:
            delta += 20
        if budget is not None:
            delta += 10
        if objection == ObjectionType.PRICE:
            delta += 10
        if urgency == UrgencyLevel.HIGH:
            delta += 20
        return delta

    @staticmethod
    def _compute_confidence(
        intent: CustomerIntent,
        objection: ObjectionType | None,
        urgency: UrgencyLevel,
        area: float | None,
        budget: int | None,
        keywords: list[str],
    ) -> int:
        score = 0
        if intent != CustomerIntent.UNCLEAR:
            score += 40
        if objection is not None:
            score += 20
        if urgency != UrgencyLevel.LOW:
            score += 15
        if area is not None:
            score += 15
        if budget is not None:
            score += 10
        if len(keywords) >= 2:
            score += 10
        return min(score, 100)

    @staticmethod
    def _fuzzy_intent(t: str) -> CustomerIntent | None:
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )

        fuzzy_map: list[tuple[tuple[str, ...], CustomerIntent]] = [
            (("narx", "narxi", "qancha", "hisobla"), CustomerIntent.WANTS_PRICE),
            (("zakaz", "buyurtma"), CustomerIntent.WANTS_ORDER),
            (("operator",), CustomerIntent.WANTS_OPERATOR),
            (("katalog", "dizayn"), CustomerIntent.WANTS_CATALOG),
            (("chegirma", "skidka"), CustomerIntent.WANTS_DISCOUNT),
        ]
        for patterns, intent in fuzzy_map:
            if TextNormalizationService.contains_fuzzy(t, patterns, max_distance=1):
                return intent
        return None

    @staticmethod
    def _fuzzy_objection(t: str) -> ObjectionType | None:
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )

        obj_fuzzy: list[tuple[tuple[str, ...], ObjectionType]] = [
            (("qimmat", "qimmatku"), ObjectionType.PRICE),
            (("kafolat", "garantiya"), ObjectionType.TRUST),
        ]
        for patterns, obj in obj_fuzzy:
            if TextNormalizationService.contains_fuzzy(t, patterns, max_distance=1):
                return obj
        return None
