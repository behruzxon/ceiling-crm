"""Slug generation utility with Cyrillic transliteration."""
from __future__ import annotations

import re
import unicodedata

# Cyrillic-to-Latin transliteration map (covers Uzbek and Russian)
_CYRILLIC_MAP: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
    # Uzbek-specific
    "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
    "'": "",
}


def generate_slug(name: str, max_length: int = 64) -> str:
    """Transliterate and slugify a business name.

    Returns lowercase alphanumeric + hyphens, max ``max_length`` chars.
    """
    text = name.lower().strip()
    result: list[str] = []
    for char in text:
        result.append(_CYRILLIC_MAP.get(char, char))
    text = "".join(result)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_length]
