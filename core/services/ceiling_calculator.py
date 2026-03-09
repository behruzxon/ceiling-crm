"""
core.services.ceiling_calculator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure FSM pricing calculation logic for the ceiling quote calculator.
Channel-agnostic — no aiogram dependency.

Extracted from apps.bot.handlers.private.pricing so the same business
rules can be called by the web API without depending on aiogram.

Public API
----------
  calculate_quote(length, width, price_per_sqm, design_name) -> CeilingQuote
  parse_dimension(text) -> float | None
  parse_two_dimensions(text) -> tuple[float, float] | None
  is_led_promo_eligible(area, design_key) -> bool
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── Promotion / discount constants ────────────────────────────────────────────

# Minimum area (m²) for the 5 % volume discount.
DISCOUNT_THRESHOLD: float = 20.0

# Minimum area (m²) for the 10 % large-area discount.
LARGE_AREA_THRESHOLD: float = 40.0

# Minimum area (m²) required for the LED strip promotional offer.
LED_PROMO_THRESHOLD: float = 50.0

# Design key that triggers the LED promo (must match DESIGN_BY_KEY in keyboards/pricing.py).
LED_PROMO_DESIGN: str = "gulli"

# Discount tiers: (area_threshold, discount_pct) — checked in order (largest first).
_TIERS: tuple[tuple[float, int], ...] = (
    (LARGE_AREA_THRESHOLD, 10),  # area > 40 m²             → 10 %
    (DISCOUNT_THRESHOLD,    5),  # area > DISCOUNT_THRESHOLD →  5 %
)

# Matches "LENGTHxWIDTH" (or *, ×, ga, spaces) with optional decimal commas/dots.
# Group 1 = length, Group 2 = width.
# Examples: "5ga4", "5*4", "5 x 4", "5 4", "5,2x3,3", "5.2 * 3.3"
TWO_DIMS_RE: re.Pattern[str] = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)"           # first number
    r"(?:\s*(?:x|×|\*|ga)\s*|\s+)"           # separator: keyword/symbol OR whitespace
    r"([0-9]+(?:[.,][0-9]+)?)\s*$",           # second number
    re.IGNORECASE,
)


# ── Quote dataclass ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CeilingQuote:
    """Immutable result of one FSM pricing calculation."""

    length: float
    width: float
    area: float
    design_name: str
    price_per_sqm: int
    gross_amount: int
    discount_pct: int
    discount_amount: int
    final_total: int

    def format_breakdown(self) -> str:
        """Return HTML-formatted price breakdown for Telegram."""
        discount_line = (
            f"\n🎁 Chegirma ({self.discount_pct}%): −{self.discount_amount:,} UZS"
            if self.discount_pct else ""
        )
        return (
            "📊 <b>Hisob-kitob natijasi</b>\n\n"
            f"📐 Uzunlik:   {self.length} m\n"
            f"📐 Kenglik:   {self.width} m\n"
            f"📐 Maydon:    <b>{self.area:.2f} m²</b>\n\n"
            f"🎨 Dizayn:    <b>{self.design_name}</b>\n"
            f"💵 Narx (m²): {self.price_per_sqm:,} UZS\n"
            f"💵 Umumiy:    {self.gross_amount:,} UZS"
            f"{discount_line}\n\n"
            f"💰 Jami: <b>{self.final_total:,} UZS</b>"
        )


# ── Pure calculation functions ─────────────────────────────────────────────────

def calculate_quote(
    length: float,
    width: float,
    price_per_sqm: int,
    design_name: str,
) -> CeilingQuote:
    """Apply tiered discount and return a fully-populated ceiling quote."""
    area = round(length * width, 2)

    discount_pct = 0
    for threshold, pct in _TIERS:
        if area > threshold:
            discount_pct = pct
            break

    gross = int(area * price_per_sqm)
    discount_amount = int(gross * discount_pct / 100)
    final_total = gross - discount_amount

    return CeilingQuote(
        length=length,
        width=width,
        area=area,
        design_name=design_name,
        price_per_sqm=price_per_sqm,
        gross_amount=gross,
        discount_pct=discount_pct,
        discount_amount=discount_amount,
        final_total=final_total,
    )


def parse_dimension(text: str | None) -> float | None:
    """
    Parse a user-supplied room dimension.
    Accepts comma or dot decimal separator.
    Returns None if the value is not a positive float in (0, 50].
    """
    try:
        v = float((text or "").replace(",", ".").strip())
    except ValueError:
        return None
    return v if 0 < v <= 50 else None


def parse_two_dimensions(text: str) -> tuple[float, float] | None:
    """Try to extract two dimensions from a single message.

    Returns ``(length, width)`` as floats, or ``None`` if fewer than two
    valid dimensions are found (caller should fall back to the step-by-step flow).
    """
    m = TWO_DIMS_RE.match(text)
    if m is None:
        return None
    a = parse_dimension(m.group(1))
    b = parse_dimension(m.group(2))
    if a is None or b is None:
        return None
    return a, b


def is_led_promo_eligible(area: float, design_key: str) -> bool:
    """Return True when the LED strip promo applies (informational only, no price change)."""
    return area >= LED_PROMO_THRESHOLD and design_key == LED_PROMO_DESIGN
