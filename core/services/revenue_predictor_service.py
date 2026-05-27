"""
core.services.revenue_predictor_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic revenue prediction for leads.

Estimates min / max / best revenue range and upsell potential based on
room dimensions, design interest, buyer type, and addon likelihood.

Reuses canonical pricing constants from ``shared.constants.pricing``.

This is a **complementary layer** — it does NOT replace the deal
probability engine's ``expected_deal_value``.  Instead it provides a
structured revenue range with upsell intelligence.

Usage::

    from core.services.revenue_predictor_service import predict_lead_revenue

    est = predict_lead_revenue(
        area_m2=22.0,
        design_type="mramor",
        buyer_type="quality_buyer",
    )
    # est.predicted_revenue_best == 2_640_000
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# ── Reuse canonical pricing constants ────────────────────────────────────────
from shared.constants.pricing import (
    ADDON_PRICES,
)
from shared.constants.pricing import (
    DEFAULT_PRICE_PER_M2 as _DEFAULT_PRICE_PER_M2,
)
from shared.constants.pricing import (
    DESIGN_PRICES_CUSTOMER as _DESIGN_PRICES,
)
from shared.constants.pricing import (
    DISCOUNT_TIERS as _DISCOUNT_TIERS,
)

# ── Cheapest / most expensive base prices for range bounds ───────────────────

_MIN_PRICE_PER_M2 = min(_DESIGN_PRICES.values())  # 80_000
_MAX_PRICE_PER_M2 = max(_DESIGN_PRICES.values())  # 140_000


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RevenueEstimate:
    """Structured revenue prediction for a lead."""

    predicted_revenue_min: int | None
    """Floor estimate in UZS (cheapest design, max discount, no addons)."""

    predicted_revenue_max: int | None
    """Ceiling estimate in UZS (current design + full addon bundle)."""

    predicted_revenue_best: int | None
    """Most likely estimate in UZS (design price + probable addons)."""

    upsell_potential: str
    """'low' | 'medium' | 'high' — how likely the customer will buy addons."""

    recommended_upsell: str
    """Uzbek-language upsell recommendation for the admin."""

    revenue_reasons: list[str] = field(default_factory=list)
    """Human-readable reasons (Uzbek) explaining the estimate."""


# ── Upsell recommendations by buyer type ─────────────────────────────────────

_UPSELL_RECS: dict[str, str] = {
    "quality_buyer": "Premium tekstura + LED RGB yoritgich",
    "fast_buyer": "Karniz + qo'shimcha yoritgich",
    "research_buyer": "Avval qo'shimchalar katalogini yuboring",
    "price_sensitive": "Asosiy dizayn, qo'shimcha taklif qilmang",
}

_DEFAULT_UPSELL = "LED yoritgich + karniz"


# ── Addon bundles (estimated cost by buyer type) ─────────────────────────────


def _estimate_addon_bundle(
    buyer_type: str | None,
    perimeter: float,
) -> tuple[int, str]:
    """Return (estimated_addon_cost, upsell_potential) for a buyer type.

    Uses canonical ``ADDON_PRICES`` from pricing_service.py.
    Perimeter is in linear meters (estimated from area).
    """
    led_strip_m = float(ADDON_PRICES["led_strip"])  # 25_000 per m
    led_rgb_m = float(ADDON_PRICES["led_rgb"])  # 40_000 per m
    cornice_m = float(ADDON_PRICES["cornice"])  # 15_000 per m
    spot_each = float(ADDON_PRICES["spot_holes"])  # 30_000 each
    chandelier = float(ADDON_PRICES["chandelier_holes"])  # 50_000 each
    rounding = float(ADDON_PRICES["profile_rounding"])  # 80_000 flat
    two_level = float(ADDON_PRICES["two_level_step"])  # 200_000 flat

    if buyer_type == "quality_buyer":
        # LED RGB + cornice + 3 spots + 1 chandelier + rounding
        cost = perimeter * led_rgb_m + perimeter * cornice_m + 3 * spot_each + chandelier + rounding
        return round(cost), "high"

    if buyer_type == "fast_buyer":
        # LED strip + cornice
        cost = perimeter * led_strip_m + perimeter * cornice_m
        return round(cost), "medium"

    if buyer_type == "research_buyer":
        # LED strip only (conservative)
        cost = perimeter * led_strip_m
        return round(cost), "medium"

    # price_sensitive or unknown — no addons
    return 0, "low"


def _get_discount(area: float) -> float:
    """Return discount fraction (0.0–0.10) based on area tiers."""
    for threshold, pct in _DISCOUNT_TIERS:
        if area > threshold:
            return pct
    return 0.0


# ── Main predictor ───────────────────────────────────────────────────────────


def predict_lead_revenue(
    *,
    area_m2: float | None = None,
    design_type: str | None = None,
    buyer_type: str | None = None,
    last_objection: str | None = None,
    closing_attempted: bool = False,
    package_type: str | None = None,
    deal_probability_percent: int | None = None,
) -> RevenueEstimate:
    """Predict revenue range for a lead from available signals.

    All parameters are keyword-only with safe defaults.
    Returns null-safe values when area is unknown.
    """
    reasons: list[str] = []

    # ── No area → null-safe return ───────────────────────────────────
    if area_m2 is None or area_m2 <= 0:
        upsell = "low"
        rec = _UPSELL_RECS.get(buyer_type or "", _DEFAULT_UPSELL)
        reasons.append("Xona o'lchami noma'lum")
        if buyer_type:
            _bt_labels = {
                "quality_buyer": "Sifat xaridori",
                "fast_buyer": "Tez qaror",
                "research_buyer": "Tadqiqotchi",
                "price_sensitive": "Narxga sezgir",
            }
            reasons.append(f"Xaridor turi: {_bt_labels.get(buyer_type, buyer_type)}")
        return RevenueEstimate(
            predicted_revenue_min=None,
            predicted_revenue_max=None,
            predicted_revenue_best=None,
            upsell_potential=upsell,
            recommended_upsell=rec,
            revenue_reasons=reasons,
        )

    # ── Perimeter estimate (assume roughly square room) ──────────────
    perimeter = 4.0 * math.sqrt(area_m2)

    reasons.append(f"Xona: {area_m2:g} m\u00b2")

    # ── Design price lookup ──────────────────────────────────────────
    if design_type:
        design_price = _DESIGN_PRICES.get(design_type.lower().strip(), _DEFAULT_PRICE_PER_M2)
        reasons.append(f"Dizayn: {design_type}")
    else:
        design_price = _DEFAULT_PRICE_PER_M2

    # ── Discount ─────────────────────────────────────────────────────
    discount = _get_discount(area_m2)

    # ── Base revenue (area × price) ──────────────────────────────────
    base_revenue = area_m2 * design_price

    # ── Addon bundle estimate ────────────────────────────────────────
    addon_cost, upsell_potential = _estimate_addon_bundle(buyer_type, perimeter)

    # ── MIN: cheapest design, max discount, no addons ────────────────
    min_discount = max(discount, 0.05)  # assume at least 5% negotiation
    rev_min = round(area_m2 * _MIN_PRICE_PER_M2 * (1 - min_discount))

    # ── MAX: current design + full addon bundle, no discount ─────────
    # Use the higher of design_price or max_price for ceiling
    max_design = max(design_price, _MAX_PRICE_PER_M2) if design_type else _MAX_PRICE_PER_M2
    # Full addon bundle (quality_buyer-level)
    full_addon, _ = _estimate_addon_bundle("quality_buyer", perimeter)
    rev_max = round(area_m2 * max_design + full_addon)

    # ── BEST: design price + probable addons - discount ──────────────
    rev_best = round((base_revenue + addon_cost) * (1 - discount))

    # ── Adjustments based on signals ─────────────────────────────────

    # Price-sensitive or expensive objection → lower best estimate
    if last_objection == "expensive" or buyer_type == "price_sensitive":
        rev_best = round(rev_best * 0.85)
        reasons.append("Narx e'tirozi — past baholash")
        upsell_potential = "low"

    # Premium design interest → raise best
    if design_type and design_type.lower().strip() in (
        "hi-tech",
        "hitech",
        "mramor",
        "naqsh",
        "kosmos",
        "qora uf",
        "qora",
        "gulli",
    ):
        reasons.append("Premium dizayn qiziqishi")

    # Closing CTA accepted → higher confidence in best
    if closing_attempted:
        reasons.append("Closing CTA qabul qilgan")

    # Package type → adjust
    if package_type == "vip":
        rev_best = round(rev_best * 1.15)
        upsell_potential = "high"
        reasons.append("VIP paket tanlangan")
    elif package_type == "premium":
        rev_best = round(rev_best * 1.08)
        if upsell_potential != "high":
            upsell_potential = "medium"
        reasons.append("Premium paket tanlangan")

    # Addon info in reasons
    if addon_cost > 0:
        reasons.append(f"Qo'shimchalar: ~{addon_cost:,} UZS")
    if discount > 0:
        reasons.append(f"Chegirma: {discount:.0%}")

    # ── Recommended upsell ───────────────────────────────────────────
    recommended_upsell = _UPSELL_RECS.get(buyer_type or "", _DEFAULT_UPSELL)

    # Ensure min <= best <= max
    rev_min = min(rev_min, rev_best)
    rev_max = max(rev_max, rev_best)

    return RevenueEstimate(
        predicted_revenue_min=rev_min,
        predicted_revenue_max=rev_max,
        predicted_revenue_best=rev_best,
        upsell_potential=upsell_potential,
        recommended_upsell=recommended_upsell,
        revenue_reasons=reasons[:5],
    )
