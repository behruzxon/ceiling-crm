"""
apps.bot.handlers.private.ai_detection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Intent / trigger detection, text parsing, and keyword dictionaries
for the AI support module.

Pure functions — no I/O, no Redis, no DB.  Safe to import anywhere.
"""

from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.utils.area_parser import parse_area as _parse_area  # noqa: F401 — re-export

# ── Measurement trigger detection ────────────────────────────────────────────

_MEASUREMENT_TRIGGERS: frozenset[str] = frozenset(
    {
        # ── Latin Uzbek — explicit order / measurement ────────────────────────────
        "yozib qo'y",
        "yozib qoʻy",
        "yozib qoy",
        "ha yozib",
        "bepul o'lchov",
        "bepul oʻlchov",
        "o'lchov kerak",
        "oʻlchov kerak",
        "o'lchov olish",
        "oʻlchov olish",
        "bepul olchov",
        "o'lchov",
        "olchov",
        "ulchov",
        "o'lchang",
        "olchang",
        "ulchang",
        "o'lchab",
        "olchab",
        "kelib o'lchang",
        "kelib olchang",
        "kelib ulchang",
        "kelib o'lchab bering",
        "kelib olchab bering",
        "o'lchab keting",
        "olchab keting",
        "usta chaqir",
        "ustani chaqir",
        "master chaqir",
        "montajchi chaqir",
        "montajchi yubor",
        "usta yuborin",
        "ustani yubor",
        "usta yubor",
        "ustani jonat",
        "usta kerak",
        # ── Latin Uzbek — order / zakaz keywords ─────────────────────────────────
        "zakaz",
        "zakaz qil",
        "zakaz qilmoqchiman",
        "zakaz oling",
        "zakaz bering",
        "buyurtma",
        "buyurtma ber",
        "buyurtma qil",
        "buyurtma qoldir",
        "qildirmoqchiman",
        "potolok qildirmoqchiman",
        "o'rnatmoqchiman",
        "oʻrnatmoqchiman",
        "ustani yuboring",
        "kelib ko'ring",
        "kelib koʻring",
        "kelinglar",
        "uyga keling",
        "uyga kelila",
        "uyga kelinglar",
        "manzilga keling",
        # ── Real-customer messy phrasings (real-language pack) ────────────────────
        "kelib korila",
        "kelib korsela",
        "kelib korila bering",
        "kelib o'lchab ketila",
        "kelib olchab ketila",
        "olchab ketila",
        "o'lchab ketila",
        "ustani jo'natila",
        "ustani jonatila",
        "usta jo'natila",
        "usta jonatila",
        "usta yuborila",
        "odam yuborila",
        "odam jo'natila",
        "odam jonatila",
        "kela olasizmi",
        "bugun kelib",
        "ertaga kela olasizmi",
        "bugun kela olasizmi",
        "manzilga kela olasizmi",
        "bermoqchiman",
        "zakaz bermoqchiman",
        "zakaz qilmoqchimiz",
        "buyurtma bermoqchiman",
        # ── Cyrillic Uzbek / Russian — order / measurement ────────────────────────
        "заказ",
        "заказ олинг",
        "заказ беринг",
        "буйуртма",
        "буйуртма бер",
        "буйуртма кил",
        "ўлчов",
        "улчов",
        "ўлчанг",
        "улчанг",
        "ўлчов керак",
        "келиб куринг",
        "келиб кўринг",
        "келиб ўлчанг",
        "келиб улчанг",
        "уста чақир",
        "устади чақир",
        "уста юбор",
        "уста юборинг",
        "манзилга келинг",
        "замер",
        "замерщик",
        "мастер",
        "вызвать мастера",
        "пришлите мастера",
    }
)


_OPERATOR_TRIGGERS: frozenset[str] = frozenset(
    {
        # ── Latin Uzbek ─────────────────────────────────────────────────────────
        "operator",
        "operatorga ulang",
        "menejer",
        "manager",
        "konsultant",
        "admin bormi",
        "admin chaqir",
        "odam bilan gaplash",
        "tirik odam",
        "jonli odam",
        "tel qil",
        "tel nomer",
        "tel raqam",
        "tel beraman",
        "aloqa qil",
        "aloqaga chiq",
        "qo'ng'iroq qil",
        "qongiroq qil",
        "qo'ng'iroq qiling",
        "qongiroq qiling",
        "usta bilan gaplash",
        # Typos
        "opratr",
        "operatr",
        "menjer",
        # ── Cyrillic Uzbek / Russian ────────────────────────────────────────────
        "оператор",
        "менеджер",
        "консультант",
        "позвоните",
        "перезвоните",
        "позвоните мне",
        "оператора",
        "связь",
        "связаться",
    }
)


def _is_operator_request(text: str) -> bool:
    """Heuristic operator-handoff detector for free-text messages.

    Lower-cases + apostrophe-unifies the input and also tries the
    Latin transliteration so Cyrillic phrases hit the Latin triggers.
    """
    lower = _normalize_for_keyword_match_safe(text)
    if any(t in lower for t in _OPERATOR_TRIGGERS):
        return True
    from shared.utils.text_normalization import latinize_uz_cyrillic

    lat = latinize_uz_cyrillic(lower)
    if lat == lower:
        return False
    return any(t in lat for t in _OPERATOR_TRIGGERS)


def _is_measurement_request(text: str) -> bool:
    lower = _normalize_for_keyword_match_safe(text)
    if any(t in lower for t in _MEASUREMENT_TRIGGERS):
        return True
    # Cyrillic fall-through: latinize the input and try again so
    # phrases like "эртага келиб ўлчанг" hit the Latin triggers
    # (kelib o'lchang / olchang / kelib ko'ring / ...).
    from shared.utils.text_normalization import latinize_uz_cyrillic

    lat = latinize_uz_cyrillic(lower)
    if lat == lower:
        return False
    return any(t in lat for t in _MEASUREMENT_TRIGGERS)


# ── Catalog link shortcut ────────────────────────────────────────────────────

_CATALOG_TRIGGERS: frozenset[str] = frozenset(
    {
        # ── Latin Uzbek — catalog / portfolio / design intent ─────────────────────
        "katalog",
        "katolog",
        "kataloq",
        "catalog",
        "portfolio",
        "variant",
        "variantlar",
        "dizayn",
        "dizaynlar",
        "design",
        "rasm",
        "foto",
        "surat",
        "namuna",
        "namunala",
        "misol",
        "ko'rsat",
        "korsat",
        "koraylik",
        "tashla",
        "yubor",
        "kanal",
        "link",
        "ishlar",
        "работы",
        # ── Real-customer typos (added in real-language pack) ───────────────────
        "katalk",
        "katalok",
        "katlog",
        "ktalog",
        # Design-name typos so "guli bormi" / "mramr korsat" still
        # enter the catalog branch (which then asks the resolver +
        # the price-intent guard keeps "guli nech pul" routed to
        # price). NOTE: do NOT add bare "bormi" / "ko'raman" here —
        # those words appear in warranty / objection messages too
        # (e.g. "kafolat bormi") and would falsely route to catalog.
        "guli",
        "gul",
        "gullili",
        "mramr",
        "marmar",
        "xaytek",
        "haytek",
        "hi tek",
        "hitek",
        "kuxnya",
        "kuhnya",
        "kitchen",
        "oshhona",
        # Cyrillic design names
        "гули",
        "гулли",
        "мармар",
        "ошхона",
        # Design type names (Latin)
        "gulli",
        "mramor",
        "naqsh",
        "hi tech",
        "hitech",
        "kosmos",
        "osmon",
        "qora uf",
        "pechat",
        # Room types — Latin
        "mehmonxona",
        "mehmon xona",
        "zal",
        "yotoqxona",
        "yotoq xona",
        "oshxona",
        "osh xona",
        "hammom",
        "dush",
        "vanna",
        "detskiy",
        "bolalar",
        "spalnya",
        "spalniy",
        "koridor",
        "terassa",
        "teras",
        "veranda",
        "balkon",
        # ── Cyrillic Uzbek ────────────────────────────────────────────────────────
        "каталог",
        "католог",
        "расм",
        "фото",
        "сурат",
        "дизайн",
        "вариант",
        "вариантлар",
        "расм юбор",
        "расм тaшла",
        "дизайн кўрсат",
        "каталог кўрсат",
        # Room types — Cyrillic
        "меҳмонхона",
        "ётоқхона",
        "ҳаммом",
    }
)


def _is_catalog_request(text: str) -> bool:
    lower = _normalize_for_keyword_match_safe(text)
    return any(t in lower for t in _CATALOG_TRIGGERS)


def _normalize_for_keyword_match_safe(text: str) -> str:
    """Same as :func:`_normalize_for_keyword_match` but defined here so
    early-loaded detectors can call it without a forward reference."""
    out = text.lower()
    for variant in ("‘", "’", "ʻ", "ʼ", "`"):
        out = out.replace(variant, "'")
    return out


# ── Catalog context detection ────────────────────────────────────────────────

_CATALOG_ROOM_KEYWORDS: dict[str, str] = {
    "mehmon xona": "Mehmonxona",
    "yotoq xona": "Yotoqxona",
    "osh xona": "Oshxona",
    "mehmonxona": "Mehmonxona",
    "yotoqxona": "Yotoqxona",
    "oshxona": "Oshxona",
    "zal": "Zal",
    "dush": "Hammom",
    "hammom": "Hammom",
    "vanna": "Hammom",
    "spalnya": "Yotoqxona",
    "spalniy": "Yotoqxona",
    "koridor": "Koridor",
    "terassa": "Terassa",
    "teras": "Terassa",
    "veranda": "Terassa",
    "balkon": "Balkon",
    "bolalar": "Bolalar xonasi",
    "detskiy": "Bolalar xonasi",
}

_CATALOG_DESIGN_KEYWORDS: dict[str, str] = {
    "gullili": "Gulli",
    "gulli": "Gulli",
    "guli": "Gulli",
    "hi tech": "Hi Tech",
    "hitech": "Hi Tech",
    "hi-tech": "Hi Tech",
    "mramor": "Mramor",
    "naqsh": "Naqsh",
    "osmon": "Osmon",
    "kosmos": "Kosmos",
    "qora uf": "Qora UF",
    "pechat": "Pechat",
    "adnatonniy": "Adnatonniy",
}


def _detect_catalog_context(text: str) -> tuple[str | None, str | None]:
    """Return (room_display_name, design_display_name) for catalog personalisation."""
    lower = text.lower()
    room: str | None = None
    design: str | None = None
    for kw in sorted(_CATALOG_ROOM_KEYWORDS, key=len, reverse=True):
        if kw in lower:
            room = _CATALOG_ROOM_KEYWORDS[kw]
            break
    for kw in sorted(_CATALOG_DESIGN_KEYWORDS, key=len, reverse=True):
        if kw in lower:
            design = _CATALOG_DESIGN_KEYWORDS[kw]
            break
    return room, design


def _build_smart_catalog_response(room: str | None, design: str | None) -> str:
    """Build a short, personalised catalog intro text."""
    context = room or design or "sizga mos"
    return (
        "Katalogimizda har xil xonalar uchun dizaynlar bor 😊\n\n"
        f"Albatta! Bizda {context} uchun ham turli dizaynlar bor.\n"
        "👇 To'liq katalogimizni shu knopkadan oching."
    )


def _catalog_link_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📂 To'liq katalogimiz", url="https://t.me/vashpotolokuz"
                ),
            ]
        ]
    )


# ── Photo funnel detection ───────────────────────────────────────────────────

_PHOTO_FUNNEL_TRIGGERS: frozenset[str] = frozenset(
    {
        "rasm",
        "foto",
        "surat",
        "dizayn",
        "variant",
        "ko'rsat",
        "korsat",
        "rasm tashla",
        "katalog",
        "portfolio",
        "namuna",
    }
)


def _is_photo_funnel_request(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in _PHOTO_FUNNEL_TRIGGERS)


# Room synonyms for photo funnel detection
_ROOM_SYNONYMS_MAP: dict[str, list[str]] = {
    "mehmonxona": ["mehmon xona", "zal", "katta xona", "terassa", "teras", "veranda"],
    "yotoqxona": ["yotoq xona", "spalniy", "spalnya", "спальня"],
    "oshxona": ["osh xona", "кухня", "kitchen"],
    "hammom": ["dush", "vanna", "sanuzel", "ванна"],
}


def _detect_room_type(text: str) -> str:
    """Detect canonical room type from user text; returns 'unknown' if not matched."""
    lower = text.lower()
    for canonical, synonyms in _ROOM_SYNONYMS_MAP.items():
        if canonical in lower:
            return canonical
        for syn in synonyms:
            if syn in lower:
                return canonical
    return "unknown"


def _room_design_text(room: str) -> str:
    """Build design recommendation text for the given room type."""
    if room == "mehmonxona":
        return (
            "Bu xona uchun tavsiya qilinadigan dizaynlar:\n\n"
            "✨ Gulli\n"
            "✨ Hi Tech\n"
            "✨ Mramor\n"
            "✨ Naqsh\n\n"
            "📌 Katalogimizda siz uchun har xil dizaynlarimiz bor 🙂"
        )
    if room == "oshxona":
        return (
            "Bu xona uchun tavsiya qilinadigan dizaynlar:\n\n"
            "✨ Hi Tech\n"
            "🌿 Gulli\n"
            "⚪ Adnatonniy\n\n"
            "💧 namlik/artib tozalash oson\n\n"
            "📌 Katalogimizda siz uchun har xil dizaynlarimiz bor 🙂"
        )
    if room == "hammom":
        return (
            "Bu xona uchun tavsiya qilinadigan dizaynlar:\n\n"
            "✨ Hi Tech\n"
            "⚪ Adnatonniy\n\n"
            "💧 namlikka chidamli\n\n"
            "📌 Katalogimizda siz uchun har xil dizaynlarimiz bor 🙂"
        )
    if room == "yotoqxona":
        return (
            "Bu xona uchun tavsiya qilinadigan dizaynlar:\n\n"
            "⚪ Adnatonniy\n"
            "☁️ Osmon\n"
            "✨ Naqsh Oq\n\n"
            "📌 Katalogimizda siz uchun har xil dizaynlarimiz bor 🙂"
        )
    return (
        "Tavsiya qilinadigan dizaynlar:\n\n"
        "✨ Mramor • ✨ Hi Tech • 🌿 Gulli\n\n"
        "📌 Katalogimizda siz uchun har xil dizaynlarimiz bor 🙂"
    )


# ── Room synonym normalisation ───────────────────────────────────────────────

_ROOM_SYNONYMS: dict[str, list[str]] = {
    "mehmonxona": ["mehmon xona", "zal", "katta xona"],
    "yotoqxona": ["yotoq xona", "spalnya"],
    "oshxona": ["osh xona", "кухня"],
    "hammom": ["vanna", "sanuzel"],
}


def _normalize_room(text: str) -> str:
    """Replace room synonyms with their canonical names (case-insensitive)."""
    lower = text.lower()
    for canonical, synonyms in _ROOM_SYNONYMS.items():
        for synonym in synonyms:
            if synonym in lower:
                text = text.lower().replace(synonym, canonical, 1)
                return text
    return text


# ── Generic confirmation intercept ───────────────────────────────────────────

_GENERIC_CONFIRMATIONS: frozenset[str] = frozenset(
    {
        "zo'r",
        "zor",
        "ok",
        "ha",
        "xo'p",
        "xop",
        "rahmat",
        "mayli",
        "bo'ldi",
        "boldi",
        "tushunarli",
        "yaxshi",
        "super",
        "ajoyib",
        "tushundim",
        "oke",
    }
)


# ── Greeting detection ───────────────────────────────────────────────────────

_GREETING_TRIGGERS: frozenset[str] = frozenset(
    {
        "salom",
        "assalomu alaykum",
        "as-salamu alaykum",
        "ассалому алайкум",
        "ассалом",
        "hello",
        "hi",
        "hey",
        "привет",
        "добрый",
    }
)


def _is_greeting(text: str) -> bool:
    """Return True if text is a greeting."""
    lower = text.lower().strip()
    return any(
        lower == g or lower.startswith(g + " ") or lower.startswith(g + ",")
        for g in _GREETING_TRIGGERS
    )


# ── Price intent detection ───────────────────────────────────────────────────

_PRICE_KEYWORDS: frozenset[str] = frozenset(
    {
        # ── Latin Uzbek ───────────────────────────────────────────────────────────
        "narx",
        "narxlar",
        "narxi qancha",
        "qancha turadi",
        "qancha pul",
        "nech pul",
        "nech pul bo'ladi",
        "nechadan qilyapsizlar",
        "qanchadan",
        "nechadan",
        "hisoblab ber",
        # ── Real-customer messy short forms (added in real-language pack) ────────
        "qancha",
        "nechi",
        "nechpul",
        "qancha boladi",
        "qancha bo'ladi",
        "qancha tushadi",
        "qancha tushyapti",
        "eng arzon",
        "eng arzoni",
        "arzoni qanaqa",
        "qaysi arzon",
        "narxini ayt",
        "narxini hisobla",
        "narxini chiqar",
        "narx kalkulyator",
        "narx hisoblash",
        "kv narx",
        "kvadrat narx",
        "m2 narx",
        # Design-specific price queries (Latin)
        "gulli qancha",
        "gulli narx",
        "hitech narx",
        "hi tech narx",
        "mramor narx",
        "naqsh narx",
        "osmon narx",
        "qora uf narx",
        "adnatonniy narx",
        # Latin transliterations of Russian
        "price",
        "stoimost",
        "skolka",
        "tsena",
        # ── Russian ───────────────────────────────────────────────────────────────
        "сколько",
        "сколько стоит",
        "цена",
        "цены",
        "рассчитать цену",
        # ── Cyrillic Uzbek ────────────────────────────────────────────────────────
        "нарх",
        "нархлар",
        "нархи канча",
        "канча туради",
        "канча пул",
        "неч пул",
        "нархи неч пул",
        "хисоблаб беринг",
        "хисоблаб бер",
        "нархини айт",
        "нархини хисобла",
        "нарх хисоблаш",
        "кв нарх",
        "квадрат нарх",
        "м2 нарх",
    }
)


def _is_price_query(text: str) -> bool:
    lower = _normalize_for_keyword_match_safe(text)
    return any(kw in lower for kw in _PRICE_KEYWORDS)


# ── Design name detection ────────────────────────────────────────────────────

_DESIGN_NAMES_IN_TEXT: dict[str, str] = {
    # ── Latin Uzbek ───────────────────────────────────────────────────────────
    "gullili": "Gulli",
    "gulli": "Gulli",
    "guli": "Gulli",
    "gul": "Gulli",
    "hi tech": "Hi Tech",
    "hitech": "Hi Tech",
    "hi-tech": "Hi Tech",
    "mramor": "Mramor",
    "naqsh": "Naqsh",
    "naxsh": "Naqsh",
    "osmon": "Osmon",
    "kosmos": "Kosmos",
    "qora uf": "Qora UF",
    "kora uf": "Qora UF",
    "adnatonniy": "Adnatonniy",
    "adnotoniy": "Adnatonniy",
    "odnotonniy": "Adnatonniy",
    "odnotoniy": "Adnatonniy",
    "pechat": "Pechat",
    # ── Cyrillic Uzbek / Russian ──────────────────────────────────────────────
    "гулли": "Gulli",
    "хай тек": "Hi Tech",
    "хайтек": "Hi Tech",
    "мрамор": "Mramor",
    "нақш": "Naqsh",
    "осмон": "Osmon",
    "космос": "Kosmos",
    "қора уф": "Qora UF",
    "аднатонний": "Adnatonniy",
    "печать": "Pechat",
    "печат": "Pechat",
}


def _extract_design_from_text(text: str) -> str | None:
    """Return canonical design name if text mentions a known design type."""
    lower = text.lower()
    for kw in sorted(_DESIGN_NAMES_IN_TEXT, key=len, reverse=True):
        if kw in lower:
            return _DESIGN_NAMES_IN_TEXT[kw]
    return None


# ── District detection ───────────────────────────────────────────────────────

_DISTRICT_ALIASES: dict[str, str] = {
    # Latin normalized (apostrophes stripped)
    "qarshi": "Qarshi",
    "shahrisabz": "Shahrisabz",
    "kitob": "Kitob",
    "yakkabog": "Yakkabog'",
    "chiroqchi": "Chiroqchi",
    "guzor": "G'uzor",
    "koson": "Koson",
    "kasbi": "Kasbi",
    "muborak": "Muborak",
    "nishon": "Nishon",
    "dehqonobod": "Dehqonobod",
    "mirishkor": "Mirishkor",
    "qamashi": "Qamashi",
    # Cyrillic Uzbek synonyms
    "яккабог": "Yakkabog'",
    "шахрисабз": "Shahrisabz",
    "карши": "Qarshi",
    "қарши": "Qarshi",
    "китоб": "Kitob",
    "чироқчи": "Chiroqchi",
    "ғузор": "G'uzor",
    "косон": "Koson",
    "касби": "Kasbi",
    "муборак": "Muborak",
    "нишон": "Nishon",
    "деҳқонобод": "Dehqonobod",
    "миришкор": "Mirishkor",
    "қамаши": "Qamashi",
}


def _normalize_for_district(text: str) -> str:
    """Lowercase and strip all apostrophe variants."""
    t = text.lower()
    for apos in ("'", "ʻ", "\u2018", "`"):
        t = t.replace(apos, "")
    return t


def detect_district(text: str) -> str | None:
    """Return canonical district name if any district alias is found in *text*."""
    normalized = _normalize_for_district(text)
    for alias in sorted(_DISTRICT_ALIASES, key=len, reverse=True):
        if alias in normalized:
            return _DISTRICT_ALIASES[alias]
    return None


# ── Combo parser ─────────────────────────────────────────────────────────────


def parse_combo(text: str) -> dict[str, Any]:
    """Extract area (m2), district and design from a single free-text message."""
    return {
        "area": _parse_area(text),
        "district": detect_district(text),
        "design": _extract_design_from_text(text),
    }


def parse_user_payload(text: str) -> dict[str, Any]:
    """Public alias for parse_combo with task-spec key names."""
    c = parse_combo(text)
    return {"area_m2": c["area"], "district": c["district"], "design_type": c["design"]}


# ── Name validation ──────────────────────────────────────────────────────────

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


def normalize_name(text: str) -> str:
    """Strip and title-case a candidate name."""
    return text.strip().title()


def is_valid_name(text: str) -> bool:
    """Return True if *text* looks like a real person's name."""
    stripped = text.strip()
    if not stripped or len(stripped) > 40:
        return False
    if any(ch.isdigit() for ch in stripped):
        return False
    if len(stripped.split()) > 3:
        return False
    lower = stripped.lower()
    return not any(kw in lower for kw in _NAME_REJECT_KEYWORDS)


# ── Price display helpers ────────────────────────────────────────────────────


def _build_price_calc(area: float) -> str:
    """Build a price calculation table for the given area in m2."""

    def _fmt(v: int) -> str:
        return f"{v:,}".replace(",", " ")

    a_str = f"{area:g}"
    return (
        f"{a_str} m² uchun taxminiy narx:\n\n"
        f"• Adnatonniy — {_fmt(int(area * 80_000))} so'm\n"
        f"• Hi Tech / Mramor / Naqsh / Kosmos / Osmon — {_fmt(int(area * 120_000))} so'm\n"
        f"• Qora UF — {_fmt(int(area * 140_000))} so'm\n"
        f"• Gulli — {_fmt(int(area * 120_000))}–{_fmt(int(area * 140_000))} so'm"
    )
