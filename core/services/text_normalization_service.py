"""
core.services.text_normalization_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic text normalization for multilingual intent detection.

Handles Uzbek Cyrillic → Latin transliteration, common typo correction,
fuzzy matching, mixed-script detection, and voice artifact normalization.
No AI — pure string operations.
"""
from __future__ import annotations

import re

from core.schemas.text_normalization import NormalizedText

# ── Uzbek Cyrillic → Latin transliteration map ───────────────────────────────
# Multi-char mappings first (checked before single-char)

_CYR_MULTI: list[tuple[str, str]] = [
    ("ш", "sh"), ("ч", "ch"), ("ю", "yu"), ("я", "ya"), ("ё", "yo"),
    ("Ш", "Sh"), ("Ч", "Ch"), ("Ю", "Yu"), ("Я", "Ya"), ("Ё", "Yo"),
]

_CYR_SINGLE: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d",
    "е": "e", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
    "қ": "q", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
    "р": "r", "с": "s", "т": "t", "у": "u", "ў": "o", "ф": "f",
    "х": "x", "ҳ": "h", "ц": "s", "ъ": "", "ь": "",
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Ғ": "G", "Д": "D",
    "Е": "E", "Ж": "J", "З": "Z", "И": "I", "Й": "Y", "К": "K",
    "Қ": "Q", "Л": "L", "М": "M", "Н": "N", "О": "O", "П": "P",
    "Р": "R", "С": "S", "Т": "T", "У": "U", "Ў": "O", "Ф": "F",
    "Х": "X", "Ҳ": "H", "Ц": "S", "Ъ": "", "Ь": "",
    "э": "e", "Э": "E",
}

# ── Common typo correction map ────────────────────────────────────────────────

_TYPO_MAP: dict[str, str] = {
    "narhi": "narxi",
    "qanca": "qancha",
    "qncha": "qancha",
    "qmat": "qimmat",
    "qimatt": "qimmat",
    "bomi": "bormi",
    "kere": "kerak",
    "kereg": "kerak",
    "opirator": "operator",
    "aperator": "operator",
    "zakas": "zakaz",
    "zakoz": "zakaz",
    "skitka": "skidka",
    "patalok": "potolok",
    "kafalat": "kafolat",
    "bermoqciman": "bermoqchiman",
}

# ── Apostrophe variants ──────────────────────────────────────────────────────

_APOSTROPHE_RE = re.compile(r"[''ʻʼ`‘’ʻʼ]")

# ── Script detection patterns ────────────────────────────────────────────────

_LATIN_RE = re.compile(r"[a-zA-Z]")
_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
_UZ_CYRILLIC_RE = re.compile(r"[ғқўҳҒҚЎҲ]")

# ── Whitespace / punctuation ─────────────────────────────────────────────────

_MULTI_SPACE_RE = re.compile(r"\s+")
_SOFT_PUNCT_RE = re.compile(r"[?!.,;:…]+$")


def _levenshtein(s: str, t: str) -> int:
    if len(s) < len(t):
        return _levenshtein(t, s)
    if len(t) == 0:
        return len(s)
    prev = list(range(len(t) + 1))
    for i, sc in enumerate(s):
        curr = [i + 1]
        for j, tc in enumerate(t):
            cost = 0 if sc == tc else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(t)]


class TextNormalizationService:
    """Deterministic text normalization for multilingual intent detection."""

    @staticmethod
    def normalize(text: str) -> NormalizedText:
        original = text
        scripts = TextNormalizationService.detect_scripts(text)
        languages = TextNormalizationService.detect_languages(text, scripts)

        n = TextNormalizationService.normalize_whitespace(text)
        n = TextNormalizationService.lower_text(n)
        n = TextNormalizationService.normalize_apostrophes(n)
        n = TextNormalizationService.strip_punctuation_soft(n)

        latin = TextNormalizationService.transliterate_uz_cyrillic_to_latin(n)
        latin, corrections = TextNormalizationService.normalize_common_typos(latin)

        tokens = TextNormalizationService.generate_tokens(latin)
        ngrams = TextNormalizationService.generate_ngrams(tokens)

        return NormalizedText(
            original=original,
            normalized=n,
            latin=latin,
            tokens=tokens,
            ngrams=ngrams,
            detected_scripts=scripts,
            detected_languages=languages,
            typo_corrections=corrections,
        )

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        return _MULTI_SPACE_RE.sub(" ", text.strip())

    @staticmethod
    def lower_text(text: str) -> str:
        return text.lower()

    @staticmethod
    def strip_punctuation_soft(text: str) -> str:
        return _SOFT_PUNCT_RE.sub("", text).strip()

    @staticmethod
    def transliterate_uz_cyrillic_to_latin(text: str) -> str:
        result = text
        for cyr, lat in _CYR_MULTI:
            result = result.replace(cyr, lat)
        chars: list[str] = []
        for ch in result:
            chars.append(_CYR_SINGLE.get(ch, ch))
        return "".join(chars)

    @staticmethod
    def normalize_apostrophes(text: str) -> str:
        return _APOSTROPHE_RE.sub("'", text)

    @staticmethod
    def normalize_common_typos(text: str) -> tuple[str, dict[str, str]]:
        corrections: dict[str, str] = {}
        tokens = text.split()
        result: list[str] = []
        for tok in tokens:
            if tok in _TYPO_MAP:
                corrections[tok] = _TYPO_MAP[tok]
                result.append(_TYPO_MAP[tok])
            else:
                result.append(tok)
        return " ".join(result), corrections

    @staticmethod
    def generate_tokens(text: str) -> list[str]:
        return [t for t in text.split() if t]

    @staticmethod
    def generate_ngrams(
        tokens: list[str],
        n: int = 2,
    ) -> list[str]:
        grams: list[str] = []
        for size in range(2, n + 1):
            for i in range(len(tokens) - size + 1):
                grams.append(" ".join(tokens[i : i + size]))
        return grams

    @staticmethod
    def contains_fuzzy(
        text: str,
        patterns: tuple[str, ...] | list[str],
        max_distance: int = 1,
    ) -> str | None:
        tokens = text.lower().split()
        for pat in patterns:
            pat_lower = pat.lower()
            for tok in tokens:
                if len(tok) < 3:
                    continue
                allowed = max_distance
                if len(pat_lower) <= 6 and max_distance > 1:
                    allowed = 1
                dist = _levenshtein(tok, pat_lower)
                if dist <= allowed:
                    return pat
        return None

    @staticmethod
    def detect_scripts(text: str) -> list[str]:
        scripts: list[str] = []
        if _LATIN_RE.search(text):
            scripts.append("latin")
        if _UZ_CYRILLIC_RE.search(text):
            scripts.append("uzbek_cyrillic")
        elif _CYRILLIC_RE.search(text):
            scripts.append("cyrillic")
        if len(scripts) > 1 or ("latin" in scripts and _CYRILLIC_RE.search(text)):
            if "mixed" not in scripts:
                scripts.append("mixed")
        return scripts or ["latin"]

    @staticmethod
    def detect_languages(
        text: str,
        scripts: list[str] | None = None,
    ) -> list[str]:
        if scripts is None:
            scripts = TextNormalizationService.detect_scripts(text)
        langs: list[str] = []
        if "uzbek_cyrillic" in scripts:
            langs.append("uzbek_cyrillic")
        if "cyrillic" in scripts and "uzbek_cyrillic" not in scripts:
            langs.append("russian")
        if "latin" in scripts:
            langs.append("uzbek_latin")
        return langs or ["unknown"]
