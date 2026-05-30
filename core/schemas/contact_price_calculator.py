"""Frozen dataclasses for the manual price calculator card in CRM
contact detail.

The calculator never touches the internal ``DEFAULT_BASE_PRICES`` map.
It uses customer-facing prices only, mirroring what the bot already
shows users.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ContactPriceCalculatorInput:
    area_m2: float | None = None
    design_key: str = ""
    addons: tuple[str, ...] = ()
    raw_area: str = ""
    raw_design: str = ""


@dataclass(frozen=True)
class ContactPriceCalculatorAddonLine:
    key: str = ""
    label: str = ""
    quantity: float = 0.0
    unit: str = ""
    unit_price_uzs: int = 0
    total_uzs: int = 0


@dataclass(frozen=True)
class ContactPriceCalculatorResult:
    is_valid: bool = False
    error: str = ""
    area_m2: float | None = None
    design_key: str = ""
    design_title: str = ""
    base_rate_uzs: int = 0
    subtotal_uzs: int = 0
    discount_percent: float = 0.0
    discount_amount_uzs: int = 0
    addon_lines: tuple[ContactPriceCalculatorAddonLine, ...] = field(default_factory=tuple)
    addons_total_uzs: int = 0
    total_uzs: int = 0
    is_estimate: bool = True
    warning: str = "Bu taxminiy hisob. Yakuniy narx o'lchovdan keyin tasdiqlanadi."
    formatted_total: str = ""
    formatted_rate: str = ""
