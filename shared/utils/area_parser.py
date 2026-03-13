"""
shared.utils.area_parser
~~~~~~~~~~~~~~~~~~~~~~~~
Robust area (m²) parser for Madina AI and pricing flows.

Accepts a wide variety of user inputs (Uzbek, Russian, English) and returns
the area in square metres as a float rounded to 2 decimal places, or None if
no valid area can be detected.

Priority:
  1. Dimension pair with explicit separator  →  a × b
  2. Dimension pair with word separator      →  a ga b / a dan b / a by b
  3. Single value + recognised area unit     →  value + unit
  4. Dimension pair with space separator     →  a b  (only when text is exactly 2 numbers)
  5. Bare integer / decimal                  →  value  (only when entire text is a number, range 2–500)

Explicitly NOT matched:
  - "2/2"  (slash — ambiguous fraction)
  - "2 2 yil" (space pair requires whole-text match)
"""
from __future__ import annotations

import re

# ── Bounds ─────────────────────────────────────────────────────────────────────
_MIN_AREA: float = 0.0
_MAX_AREA: float = 10_000.0

# Narrower bounds for ambiguous patterns (space-pair and bare number)
_MIN_AREA_STRICT: float = 1.99   # effectively >= 2
_MAX_AREA_STRICT: float = 500.0

# ── Number token ───────────────────────────────────────────────────────────────
# Matches integers or decimals with dot or comma as decimal separator.
_N = r"(\d+(?:[.,]\d+)?)"

# ── Dimension pair — symbol separators (x / × / *) ────────────────────────────
# Matches: "2x2", "2 * 2", "3.5×4", "3,5 x 4", "2X2"
_DIM_SYMBOL_RE: re.Pattern[str] = re.compile(
    rf"{_N}\s*[xX×*]\s*{_N}",
    re.IGNORECASE,
)

# ── Dimension pair — word separators (ga / dan / by) ──────────────────────────
# Matches: "2 ga 2", "2ga2", "2 dan 2", "2dan2", "2 by 2", "2by2"
_DIM_WORD_RE: re.Pattern[str] = re.compile(
    rf"{_N}\s*(?:ga|dan|by)\s*{_N}",
    re.IGNORECASE,
)

# ── Single value + area unit ───────────────────────────────────────────────────
# Ordered longest-first to prevent partial matches
# (e.g. "кв.м" must come before "кв", "kvadrat metr" before "kvadrat").
_UNIT_RE: re.Pattern[str] = re.compile(
    rf"{_N}\s*"
    r"(?:"
    r"metr\s+kvadrat"    # "30 metr kvadrat"
    r"|kvadrat\s+metr"   # "30 kvadrat metr"
    r"|kvadrat"          # "30 kvadrat"
    r"|kvm"              # "30kvm"
    r"|kv"               # "30kv" / "30 kv"
    r"|m\s*2"            # "30m2" / "30 m 2" / "30 m2"
    r"|m²"               # "30m²"
    r"|м\s*2"            # "30м2" / "30 м2" (Cyrillic м)
    r"|квадрат"          # "30 квадрат"
    r"|кв\.м"            # "30 кв.м"
    r"|квм"              # "30квм"
    r"|кв"               # "30кв" / "30 кв"
    r")",
    re.IGNORECASE,
)


# ── Dimension pair — whole-text space separator ("2 2", "3 4") ────────────────
# Only matches when the ENTIRE text is exactly two numbers separated by space.
# This avoids false positives in long sentences.
_DIM_SPACE_RE: re.Pattern[str] = re.compile(
    rf"^\s*{_N}\s+{_N}\s*$",
    re.IGNORECASE,
)

# ── Bare integer/decimal (last resort) ────────────────────────────────────────
# Matches when the entire stripped text is a single number (e.g. "20", "150").
_BARE_NUM_RE: re.Pattern[str] = re.compile(
    rf"^\s*{_N}\s*$",
    re.IGNORECASE,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_float(s: str) -> float | None:
    """Convert a numeric token (comma or dot decimal) to float."""
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _bounded(value: float) -> float | None:
    """Return value rounded to 2 dp if within (0, _MAX_AREA], else None."""
    if _MIN_AREA < value <= _MAX_AREA:
        return round(value, 2)
    return None


def _bounded_strict(value: float) -> float | None:
    """Return value rounded to 2 dp if within [2, 500], else None."""
    if _MIN_AREA_STRICT < value <= _MAX_AREA_STRICT:
        return round(value, 2)
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def parse_area(text: str) -> float | None:
    """Parse a square-metre area value from free-form user text.

    Supported dimension pairs (a × b → area = a * b):
        "5x4"  "5 * 4"  "5×4"  "3.5 x 4"  "3,5×4"
        "5 ga 4"  "5ga4"  "5 dan 4"  "5dan4"  "5 by 4"
        "5 4"  (whole-text space pair, range 2–500)

    Supported single value + unit:
        "30kv"  "30 kv"  "30kvadrat"  "30 kvadrat"  "30 kvadrat metr"
        "30m2"  "30 m2"  "30 m 2"  "30m²"  "30 metr kvadrat"
        "30 квадрат"  "30 кв"  "30 кв.м"  "30кв"  "30квм"

    Bare number (whole-text, range 2–500):
        "20"  "150"

    Decimal separator: "." or "," accepted.

    Not matched:
        "2/2"  →  None  (slash excluded — ambiguous fraction)
        "2 2 yil" →  None  (space pair requires whole-text match)

    Returns:
        float  — area in m², rounded to 2 decimal places.
        None   — no valid area detected, or value out of range.
    """
    text = text.strip()

    # 1. Dimension pair — symbol separators: x, ×, *
    m = _DIM_SYMBOL_RE.search(text)
    if m:
        a = _to_float(m.group(1))
        b = _to_float(m.group(2))
        if a is not None and b is not None:
            result = _bounded(a * b)
            if result is not None:
                return result

    # 2. Dimension pair — word separators: ga, dan, by
    m = _DIM_WORD_RE.search(text)
    if m:
        a = _to_float(m.group(1))
        b = _to_float(m.group(2))
        if a is not None and b is not None:
            result = _bounded(a * b)
            if result is not None:
                return result

    # 3. Single value + recognised area unit
    m = _UNIT_RE.search(text)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return _bounded(v)

    # 4. Whole-text space-separated dimension pair: "5 4" → 20 m² (range 2–500)
    m = _DIM_SPACE_RE.match(text)
    if m:
        a = _to_float(m.group(1))
        b = _to_float(m.group(2))
        if a is not None and b is not None:
            result = _bounded_strict(a * b)
            if result is not None:
                return result

    # 5. Bare number (last resort) — only when entire text is one number (range 2–500)
    m = _BARE_NUM_RE.match(text)
    if m:
        v = _to_float(m.group(1))
        if v is not None:
            return _bounded_strict(v)

    return None
