"""
shared.utils.text_normalization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pure, deterministic normalization helpers for messy customer input.

Two public functions:

* :func:`latinize_uz_cyrillic` — best-effort character-level
  transliteration from Uzbek/Russian Cyrillic to a Latin
  approximation that matches the spelling the rest of the bot uses.
* :func:`normalize_customer_text` — lowercase, collapse whitespace,
  unify apostrophe variants, and optionally latinize Cyrillic.

These helpers contain no I/O and no dependencies outside the
standard library. They are safe to call from any layer.
"""

from __future__ import annotations

import re

# Cyrillic → Latin character map. Order matters for the few digraphs
# that are handled separately below; this dict covers single characters.
_CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "ғ": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "j",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "қ": "q",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "ў": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "x",
    "ҳ": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sh",
    "ъ": "",
    "ы": "i",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

# Digraphs and known multi-char patterns checked before the per-char
# pass. The right-hand side is the spelling the rest of the bot
# expects.
_CYRILLIC_DIGRAPHS: tuple[tuple[str, str], ...] = (
    ("хай тек", "hi tech"),
    ("хай-тек", "hi-tech"),
    ("хайтек", "hitech"),
    ("хи тек", "hi tech"),
    ("уф печать", "uf pechat"),
    ("печать", "pechat"),
    ("чор", "chor"),
    ("ҳаммом", "hammom"),
    ("меҳмонхона", "mehmonxona"),
    ("ётоқхона", "yotoqxona"),
    ("ошхона", "oshxona"),
    ("каталог", "katalog"),
    ("католог", "katalog"),
    ("дизайн", "dizayn"),
    ("вариант", "variant"),
    ("расм", "rasm"),
    ("фото", "foto"),
)

# Apostrophe variants users type — collapsed to the ASCII apostrophe
# so alias tables don't need to enumerate every Unicode codepoint.
_APOSTROPHE_VARIANTS: tuple[str, ...] = (
    "‘",  # ‘
    "’",  # ’
    "ʻ",  # ʻ
    "ʼ",  # ʼ
    "`",
)


def latinize_uz_cyrillic(text: str | None) -> str:
    """Best-effort Cyrillic → Latin transliteration."""
    if not text:
        return ""
    out = text.lower()
    # Pass 1: known digraphs / multi-char patterns.
    for src, dst in _CYRILLIC_DIGRAPHS:
        if src in out:
            out = out.replace(src, dst)
    # Pass 2: per-character.
    out = "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in out)
    return out


_WS_RE = re.compile(r"\s+")


def normalize_customer_text(text: str | None, *, latinize: bool = True) -> str:
    """Lowercase, unify apostrophes, collapse whitespace, optional latinize.

    Returns ``""`` for ``None`` / empty input.
    """
    if not text:
        return ""
    out = text.lower().strip()
    for variant in _APOSTROPHE_VARIANTS:
        out = out.replace(variant, "'")
    # Convert dashes to spaces only when they sit between words (keep
    # "hi-tech" intact because the alias table also has the dashed
    # form). Operate after lowercasing.
    if latinize:
        out = latinize_uz_cyrillic(out)
    out = _WS_RE.sub(" ", out)
    return out


__all__ = ["latinize_uz_cyrillic", "normalize_customer_text"]
