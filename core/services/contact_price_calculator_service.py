"""
core.services.contact_price_calculator_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Thin pure helper that powers the *Manual Price Calculator* card on the
CRM contact-detail page.

Wraps the existing :class:`core.services.price_calculator_service.
PriceCalculatorService` so the CRM web layer doesn't reinvent rate or
discount logic. The wrapper is **read-only**: it never writes a row,
never calls AI, never calls Telegram, and never reads or exposes the
per-category internal-quote price map (those are reserved for real
quote generation, not for the operator UI).
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from core.schemas.contact_price_calculator import (
    ContactPriceCalculatorAddonLine,
    ContactPriceCalculatorResult,
)
from core.services.price_calculator_service import (
    MAX_AREA,
    MIN_AREA,
    PriceCalculatorService,
)
from shared.constants.pricing import ADDON_PRICES, DESIGN_PRICES_CUSTOMER

# Subset of ADDON_PRICES the calculator UI surfaces. Keys must match
# ADDON_PRICES keys exactly. The label is the operator-facing display
# name; the unit / qty function decides how the addon scales with area.
_ADDON_CATALOG: tuple[dict, ...] = (
    {"key": "led_strip", "label": "LED strip", "unit": "m", "scale": "perimeter"},
    {"key": "led_rgb", "label": "LED RGB", "unit": "m", "scale": "perimeter"},
    {"key": "cornice", "label": "Plintus / Cornice", "unit": "m", "scale": "perimeter"},
    {"key": "chandelier_holes", "label": "Lyustra teshigi", "unit": "dona", "scale": "one"},
    {"key": "spot_holes", "label": "Spot teshigi", "unit": "dona", "scale": "one"},
    {"key": "profile_rounding", "label": "Profil yumaloqlash", "unit": "shtuk", "scale": "flat"},
    {"key": "two_level_step", "label": "Ikki yarus", "unit": "shtuk", "scale": "flat"},
)

_ADDON_BY_KEY = {a["key"]: a for a in _ADDON_CATALOG}

_DEFAULT_DESIGN = "adnatonniy"  # safest default rate (lowest customer-facing)

_DEFAULT_WARNING = "Bu taxminiy hisob. Yakuniy narx o'lchovdan keyin tasdiqlanadi."


def _parse_area(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip().replace(",", ".")
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            parsed = PriceCalculatorService.parse_area_from_text(text)
            if parsed is None:
                return None
            value = float(parsed)
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def _resolve_design(raw: str | None) -> str:
    if not raw:
        return _DEFAULT_DESIGN
    text = str(raw).strip().lower()
    if not text:
        return _DEFAULT_DESIGN
    if text in DESIGN_PRICES_CUSTOMER:
        return text
    parsed = PriceCalculatorService.parse_design_from_text(text)
    if parsed and parsed in DESIGN_PRICES_CUSTOMER:
        return parsed
    return _DEFAULT_DESIGN


def _parse_addons(
    raw: Iterable[str] | str | None,
) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        items = [chunk.strip().lower() for chunk in raw.split(",")]
    else:
        items = [str(chunk).strip().lower() for chunk in raw]
    seen: list[str] = []
    for item in items:
        if not item:
            continue
        if item not in _ADDON_BY_KEY:
            continue
        if item in seen:
            continue
        seen.append(item)
    return tuple(seen)


def _format_uzs(amount: int) -> str:
    return f"{int(max(0, amount)):,}".replace(",", " ")


def _addon_quantity(scale: str, perimeter_m: float) -> float:
    if scale == "perimeter":
        return round(perimeter_m, 2)
    if scale == "one":
        return 1.0
    if scale == "flat":
        return 1.0
    return 0.0


def build_contact_price_estimate(
    area_m2: str | float | int | None = None,
    design_key: str | None = None,
    addons: Iterable[str] | str | None = None,
) -> ContactPriceCalculatorResult:
    """Build a taxminiy estimate for the operator UI.

    Read-only. Returns an invalid result with a friendly error when
    the input is missing or out of bounds — the template renders the
    error inline and keeps the form usable.
    """
    parsed_addons = _parse_addons(addons)
    parsed_area = _parse_area(area_m2)

    if parsed_area is None:
        return ContactPriceCalculatorResult(
            is_valid=False,
            error="Maydonni kiriting (m²). Masalan: 20.",
            design_key=_resolve_design(design_key),
        )

    if parsed_area < MIN_AREA:
        return ContactPriceCalculatorResult(
            is_valid=False,
            error="Maydon juda kichik. Kamida 1 m² kiriting.",
            area_m2=parsed_area,
            design_key=_resolve_design(design_key),
        )

    if parsed_area > MAX_AREA:
        return ContactPriceCalculatorResult(
            is_valid=False,
            error="Maydon juda katta. Maksimum 500 m².",
            area_m2=parsed_area,
            design_key=_resolve_design(design_key),
        )

    canonical_design = _resolve_design(design_key)
    base_estimate = PriceCalculatorService().calculate_estimate(parsed_area, canonical_design)

    perimeter_m = 4.0 * math.sqrt(parsed_area)
    addon_lines: list[ContactPriceCalculatorAddonLine] = []
    addons_total = 0
    for key in parsed_addons:
        spec = _ADDON_BY_KEY[key]
        unit_price = int(ADDON_PRICES[key])
        qty = _addon_quantity(spec["scale"], perimeter_m)
        line_total = int(max(0, qty * unit_price))
        addon_lines.append(
            ContactPriceCalculatorAddonLine(
                key=key,
                label=spec["label"],
                quantity=qty,
                unit=spec["unit"],
                unit_price_uzs=unit_price,
                total_uzs=line_total,
            )
        )
        addons_total += line_total

    total = max(0, base_estimate.total_uzs + addons_total)

    return ContactPriceCalculatorResult(
        is_valid=True,
        error="",
        area_m2=parsed_area,
        design_key=canonical_design,
        design_title=base_estimate.design_title,
        base_rate_uzs=base_estimate.rate_uzs_per_m2,
        subtotal_uzs=base_estimate.subtotal_uzs,
        discount_percent=base_estimate.discount_percent,
        discount_amount_uzs=base_estimate.discount_amount_uzs,
        addon_lines=tuple(addon_lines),
        addons_total_uzs=addons_total,
        total_uzs=total,
        is_estimate=True,
        warning=_DEFAULT_WARNING,
        formatted_total=_format_uzs(total),
        formatted_rate=_format_uzs(base_estimate.rate_uzs_per_m2),
    )


def available_designs() -> tuple[tuple[str, str], ...]:
    """Return (key, friendly_label) pairs the UI can show in a <select>."""
    seen: dict[str, str] = {}
    for key in DESIGN_PRICES_CUSTOMER:
        if key in seen:
            continue
        seen[key] = key.title()
    return tuple(seen.items())


def available_addons() -> tuple[tuple[str, str], ...]:
    return tuple((a["key"], a["label"]) for a in _ADDON_CATALOG)
