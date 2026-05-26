"""
shared.constants.pricing
~~~~~~~~~~~~~~~~~~~~~~~~~
Single source of truth for all pricing constants used across the project.

There are **two intentionally different** price tiers — do NOT merge them:

1. ``DEFAULT_BASE_PRICES`` — per-category quote calculation prices
   (100k–300k UZS/m²).  Used by ``PricingService`` to generate real
   customer quotes.  Keyed by ``CeilingCategory`` enum.

2. ``DESIGN_PRICES_CUSTOMER`` — customer-facing / AI display prices
   (80k–140k UZS/m²).  Used by the deal probability engine and revenue
   predictor for quick estimates and AI conversation context.
   Keyed by lowercase design-name strings.
"""
from __future__ import annotations

from decimal import Decimal

from shared.constants.enums import CeilingCategory

# ── Quote calculation prices (internal, per category) ────────────────────────

DEFAULT_BASE_PRICES: dict[CeilingCategory, Decimal] = {
    CeilingCategory.ODNOTONNY:     Decimal("120000"),
    CeilingCategory.NAQSH_OQ:      Decimal("130000"),
    CeilingCategory.QORA_NAQSH_UF: Decimal("180000"),
    CeilingCategory.GULLI:         Decimal("250000"),
    CeilingCategory.MRAMOR:        Decimal("220000"),
    CeilingCategory.HI_TECH:       Decimal("200000"),
    CeilingCategory.KOSMOS:        Decimal("300000"),
    CeilingCategory.NAQSH_RAMKA:   Decimal("280000"),
    CeilingCategory.OSMON:         Decimal("100000"),
    CeilingCategory.OSHXONA:       Decimal("140000"),
}

# ── Add-on unit prices (UZS) ────────────────────────────────────────────────

ADDON_PRICES: dict[str, Decimal] = {
    "led_strip":        Decimal("25000"),   # per linear meter
    "led_rgb":          Decimal("40000"),   # per linear meter
    "chandelier_holes": Decimal("50000"),   # per hole
    "spot_holes":       Decimal("30000"),   # per hole
    "cornice":          Decimal("15000"),   # per linear meter
    "profile_rounding": Decimal("80000"),   # flat fee
    "two_level_step":   Decimal("200000"),  # flat fee
}

# ── Customer-facing / AI display prices (per design name) ───────────────────

DESIGN_PRICES_CUSTOMER: dict[str, int] = {
    "adnatonniy": 80_000,
    "matt":       80_000,
    "hi-tech":    120_000,
    "hitech":     120_000,
    "mramor":     120_000,
    "naqsh":      120_000,
    "kosmos":     120_000,
    "osmon":      120_000,
    "gulli":      130_000,
    "qora uf":    140_000,
    "qora":       140_000,
}

DEFAULT_PRICE_PER_M2: int = 100_000  # average when design unknown

# ── Discount tiers ──────────────────────────────────────────────────────────

DISCOUNT_TIERS: tuple[tuple[float, float], ...] = (
    (40.0, 0.10),   # area > 40 m² → 10 %
    (20.0, 0.05),   # area > 20 m² → 5 %
)
