"""
core.services.catalog_link_resolver_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Confidence-based resolver for design-specific catalog deep links.

Matching strategy:

1. Exact alias hit after normalization → confidence ``100``.
2. Cyrillic-latinized exact alias hit  → confidence ``95``.
3. Known typo / short-form alias hit   → confidence ``90``.
4. Fuzzy edit-distance via ``difflib.SequenceMatcher`` —
   ratio ≥ 0.85 → confidence ``80`` (direct);
   ratio 0.70–0.85 with a single best candidate → confidence ``70``
   (confirmation required).
5. Ambiguous phrase (e.g. bare "naqsh") → ``needs_confirmation`` with
   2–3 candidate buttons.
6. Nothing matched → fall back to the generic full-catalog link if
   the text otherwise looks like a catalog request, else no action.

URLs are **never** invented — every link comes from
``shared.constants.catalog.CATALOG_BY_KEY``.
"""

from __future__ import annotations

import difflib
import re

from core.schemas.catalog_link import CatalogLink, CatalogLinkResult
from shared.constants.catalog import CATALOG_BY_KEY
from shared.utils.text_normalization import (
    latinize_uz_cyrillic,
    normalize_customer_text,
)

# Defence-in-depth: even though the resolver only echoes a short
# source-text preview back into its result, redact anything that
# looks like a secret so the field can be safely logged / shown.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "[redacted_openai_key]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{4,}"), "[redacted_bearer]"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"), "[redacted_bot_token]"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+"), "[redacted_db_url]"),
    (re.compile(r"redis://[^\s\"']+"), "[redacted_redis_url]"),
    (re.compile(r"\bBOT_TOKEN\b", re.I), "[redacted_marker]"),
    (re.compile(r"\bOPENAI\b", re.I), "[redacted_marker]"),
    (re.compile(r"\bDATABASE_URL\b", re.I), "[redacted_marker]"),
)

# Generic full-catalog URL.
_GENERIC_URL = "https://t.me/vashpotolokuz"
_GENERIC_TITLE = "📂 To'liq katalog"

_DIRECT_CONFIDENCE_THRESHOLD = 90
_CONFIRMATION_LOWER_BOUND = 70

_MAX_PREVIEW = 80


# Aliases per catalog key. The resolver iterates the **flattened**
# list with longest-first ordering so multi-word phrases ("naqsh oq"
# / "qora naqsh") win before bare single words ("naqsh").
_ALIASES_BY_KEY: dict[str, tuple[str, ...]] = {
    "gulli": (
        "gulli",
        "guli",
        "gull",
        "gullli",
        "gulliy",
        "gullili",
        "gul",
    ),
    "odnotonniy": (
        "odnotonniy",
        "odnoton",
        "odnaton",
        "odnotonny",
        "odnatonniy",
        "adnatonniy",
        "adnatoniy",
        "adnatoni",
        "oddiy",
        "bir xil",
        "matoviy",
        "matt",
        "satin",
    ),
    "mramor": (
        "mramor",
        "mromor",
        "mramoor",
        "marmar",
        "mar-mar",
        "marble",
    ),
    "qora_naqsh_uf": (
        "qora naqsh",
        "qora uf",
        "kora naqsh",
        "kora nakh",
        "kora nakhs",
        "kora naks",
        "uf pechat",
        "uf print",
        "qora pechat",
        "uf",
        "pechat",
        "print",
    ),
    "hi_tech": (
        "hi tech",
        "hi-tech",
        "hitech",
        "hi tek",
        "hitek",
        "haytek",
        "xaytek",
        "led",
        "shadow",
    ),
    "kosmos": (
        "kosmos",
        "kosmoss",
        "kosmosli",
        "cosmos",
    ),
    "osmon": (
        "osmon",
        "osmmon",
        "osmonli",
        "nebo",
        "sky",
    ),
    "oshxona": (
        "oshxona",
        "oshhona",
        "osh xona",
        "oxxona",
        "kuxnya",
        "kuhnya",
        "kuxnia",
        "kitchen",
    ),
    "naqsh_ramka": (
        "naqsh ramka",
        "naqshramka",
        "ramkali naqsh",
        "ramka",
    ),
    "naqsh_oq": (
        "naqsh oq",
        "oq naqsh",
        "ok nakh",
        "ok naks",
        "ok",
        "oq",
        "white",
    ),
}

# When the user types a bare ambiguous word, expand to the candidate
# keys so the UI can ask which one.
_AMBIGUOUS_TRIGGERS: dict[str, tuple[str, ...]] = {
    "naqsh": ("naqsh_oq", "naqsh_ramka", "qora_naqsh_uf"),
}

# Catalog-request words that signal "user wants a catalog" even if no
# specific design alias is mentioned. Used for the generic fallback.
_GENERIC_CATALOG_TRIGGERS: frozenset[str] = frozenset(
    {
        "katalog",
        "kataloq",
        "catalog",
        "rasm",
        "foto",
        "surat",
        "namuna",
        "ko'rsat",
        "korsat",
        "tashla",
        "yubor",
        "dizayn",
        "dizaynlar",
        "variant",
        "variantlar",
        "portfolio",
    }
)


# ── Pre-built alias index (sorted by length desc) ─────────────────────


def _build_alias_index() -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for key, aliases in _ALIASES_BY_KEY.items():
        for alias in aliases:
            pairs.append((alias.lower(), key))
    pairs.sort(key=lambda p: (-len(p[0]), p[0]))
    return tuple(pairs)


_ALIAS_INDEX: tuple[tuple[str, str], ...] = _build_alias_index()


# ── Public API ─────────────────────────────────────────────────────────


def resolve_catalog_link(text: str | None) -> CatalogLinkResult:
    """Return the best-matching catalog deep link for ``text``.

    Pure: no I/O. Safe to call from any layer.
    """
    fallback = _make_fallback()
    preview = _make_preview(text)

    normalised = normalize_customer_text(text or "")
    if not normalised:
        return CatalogLinkResult(
            matched=False,
            fallback_link=fallback,
            intro_text="Mana to'liq katalogimiz 👇",
            reason="empty_text",
            source_text_preview=preview,
        )

    # ── (1)+(2) exact alias on normalized (already Cyrillic-latinized)
    for alias, key in _ALIAS_INDEX:
        if alias in normalised:
            confidence = _confidence_for_alias(text or "", alias)
            return _result_direct(
                key,
                confidence=confidence,
                fallback=fallback,
                preview=preview,
                reason=f"alias:{alias}",
            )

    # ── (5) ambiguous bare triggers
    for trigger, candidate_keys in _AMBIGUOUS_TRIGGERS.items():
        if trigger in normalised:
            candidates = tuple(_link_for(k) for k in candidate_keys if _link_for(k) is not None)
            return CatalogLinkResult(
                matched=False,
                needs_confirmation=True,
                confidence=60,
                candidates=tuple(c for c in candidates if c is not None),
                fallback_link=fallback,
                intro_text="Siz qaysi katalogni nazarda tutdingiz?",
                confirmation_question="Siz qaysi katalogni nazarda tutdingiz?",
                source_text_preview=preview,
                reason=f"ambiguous:{trigger}",
            )

    # ── (4) fuzzy match
    best_key, best_ratio = _best_fuzzy(normalised)
    if best_key and best_ratio >= 0.85:
        confidence = 80
        return _result_direct(
            best_key,
            confidence=confidence,
            fallback=fallback,
            preview=preview,
            reason=f"fuzzy:{best_ratio:.2f}",
        )
    if best_key and best_ratio >= 0.70:
        link = _link_for(best_key)
        if link is not None:
            return CatalogLinkResult(
                matched=False,
                needs_confirmation=True,
                confidence=70,
                candidates=(link,),
                fallback_link=fallback,
                intro_text=f"Siz {link.title} katalogini nazarda tutdingizmi?",
                confirmation_question=f"Siz {link.title} katalogini nazarda tutdingizmi?",
                source_text_preview=preview,
                reason=f"fuzzy_confirm:{best_ratio:.2f}",
            )

    # ── (6) generic fallback when text looks like a catalog ask
    if any(word in normalised for word in _GENERIC_CATALOG_TRIGGERS):
        return CatalogLinkResult(
            matched=False,
            fallback_link=fallback,
            intro_text="Mana to'liq katalogimiz 👇",
            source_text_preview=preview,
            reason="generic_catalog_trigger",
        )

    # ── otherwise: nothing
    return CatalogLinkResult(
        matched=False,
        fallback_link=fallback,
        intro_text="Mana to'liq katalogimiz 👇",
        source_text_preview=preview,
        reason="no_alias",
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _confidence_for_alias(original_text: str, alias: str) -> int:
    """Choose between confidence 100 / 95 / 90 based on how much the
    original needed to be transformed to hit the alias."""
    raw_lower = (original_text or "").lower()
    if alias in raw_lower:
        return 100
    latin = latinize_uz_cyrillic(raw_lower)
    if alias in latin:
        return 95
    return 90


def _result_direct(
    key: str,
    *,
    confidence: int,
    fallback: CatalogLink,
    preview: str,
    reason: str,
) -> CatalogLinkResult:
    section = CATALOG_BY_KEY.get(key)
    if section is None:
        return CatalogLinkResult(
            matched=False,
            confidence=0,
            fallback_link=fallback,
            intro_text="Mana to'liq katalogimiz 👇",
            source_text_preview=preview,
            reason=f"missing_section:{key}",
        )
    if not section.group_url:
        return CatalogLinkResult(
            matched=True,
            confidence=confidence,
            link=CatalogLink(key=section.key, title=section.title, url=""),
            fallback_link=fallback,
            intro_text=(
                f"Bu bo'lim ({section.title}) uchun alohida link hali "
                "sozlanmagan. Mana to'liq katalogimiz 👇"
            ),
            source_text_preview=preview,
            reason="link_missing",
        )
    link = CatalogLink(key=section.key, title=section.title, url=section.group_url)
    return CatalogLinkResult(
        matched=True,
        confidence=confidence,
        link=link,
        fallback_link=fallback,
        intro_text=f"Albatta, mana {section.title} katalogimiz 👇",
        source_text_preview=preview,
        reason=reason,
    )


def _link_for(key: str) -> CatalogLink | None:
    section = CATALOG_BY_KEY.get(key)
    if section is None:
        return None
    return CatalogLink(key=section.key, title=section.title, url=section.group_url)


def _best_fuzzy(normalised: str) -> tuple[str | None, float]:
    """Score each alias against each token in ``normalised`` and return
    the (key, ratio) of the best match. Single-letter aliases ignored
    so noise doesn't trigger them."""
    tokens = [tok for tok in normalised.split() if tok and len(tok) > 2]
    best_ratio = 0.0
    best_key: str | None = None
    for alias, key in _ALIAS_INDEX:
        if len(alias) < 4:
            continue
        for tok in tokens:
            ratio = difflib.SequenceMatcher(None, alias, tok).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_key = key
    return best_key, best_ratio


def _make_fallback() -> CatalogLink:
    return CatalogLink(key="all", title=_GENERIC_TITLE, url=_GENERIC_URL)


def _make_preview(text: str | None) -> str:
    if not text:
        return ""
    snippet = text.strip().replace("\n", " ")
    for pattern, replacement in _SECRET_PATTERNS:
        snippet = pattern.sub(replacement, snippet)
    if len(snippet) > _MAX_PREVIEW:
        snippet = snippet[: _MAX_PREVIEW - 1].rstrip() + "…"
    return snippet


__all__ = ["resolve_catalog_link"]
