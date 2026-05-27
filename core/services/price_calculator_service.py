"""Deterministic price calculator — single source of truth for estimates.

Uses DESIGN_PRICES_CUSTOMER for customer-facing calculations.
Internal quote prices (DEFAULT_BASE_PRICES) are NOT used here.
"""
from __future__ import annotations

import re
from typing import Any

from core.schemas.price_calculator import (
    PriceCalculatorResponse,
    PriceClarificationResult,
    PriceEstimateResult,
)
from shared.constants.pricing import (
    DEFAULT_PRICE_PER_M2,
    DESIGN_PRICES_CUSTOMER,
    DISCOUNT_TIERS,
)
from shared.utils.area_parser import parse_area

_DESIGN_ALIASES: dict[str, str] = {
    "oddiy": "adnatonniy",
    "matoviy": "adnatonniy",
    "matt": "matt",
    "satin": "adnatonniy",
    "adnatonniy": "adnatonniy",
    "gulli": "gulli",
    "gullili": "gulli",
    "print": "gulli",
    "pechat": "gulli",
    "led": "hi-tech",
    "shadow": "hi-tech",
    "hi-tech": "hi-tech",
    "hitech": "hi-tech",
    "hi tech": "hi-tech",
    "mramor": "mramor",
    "naqsh": "naqsh",
    "kosmos": "kosmos",
    "osmon": "osmon",
    "qora": "qora uf",
    "qora uf": "qora uf",
    "oshxona": "osmon",
}

_DESIGN_TITLES: dict[str, str] = {
    "adnatonniy": "Adnatonniy (oddiy)",
    "matt": "Adnatonniy (oddiy)",
    "gulli": "Gulli",
    "hi-tech": "Hi-tech",
    "mramor": "Mramor",
    "naqsh": "Naqsh",
    "kosmos": "Kosmos",
    "osmon": "Osmon",
    "qora uf": "Qora UF",
}

MIN_AREA = 1.0
MAX_AREA = 500.0

_TOKEN_RE = re.compile(r"(sk-[a-zA-Z0-9]{8,}|Bearer\s+\S{10,})", re.I)


class PriceCalculatorService:

    @staticmethod
    def parse_area_from_text(text: str) -> float | None:
        area = parse_area(text)
        if area is not None and area < MIN_AREA:
            return None
        if area is not None and area > MAX_AREA:
            return None
        return area

    @staticmethod
    def parse_design_from_text(text: str) -> str | None:
        lower = text.lower()
        for alias in sorted(_DESIGN_ALIASES, key=len, reverse=True):
            if alias in lower:
                return _DESIGN_ALIASES[alias]
        return None

    @staticmethod
    def get_rate(design_key: str) -> int:
        return DESIGN_PRICES_CUSTOMER.get(design_key, DEFAULT_PRICE_PER_M2)

    @staticmethod
    def calculate_discount(area_m2: float) -> tuple[float, int, int]:
        for threshold, pct in DISCOUNT_TIERS:
            if area_m2 > threshold:
                return pct, 0, 0
        return 0.0, 0, 0

    def calculate_estimate(
        self,
        area_m2: float,
        design_key: str,
    ) -> PriceEstimateResult:
        rate = self.get_rate(design_key)
        subtotal = int(area_m2 * rate)
        discount_pct = 0.0
        for threshold, pct in DISCOUNT_TIERS:
            if area_m2 > threshold:
                discount_pct = pct * 100
                break
        discount_amount = int(subtotal * discount_pct / 100)
        total = subtotal - discount_amount
        title = _DESIGN_TITLES.get(design_key, design_key.title())
        warnings = [
            "Bu taxminiy hisob.",
            "Yakuniy narx o'lchov va material bo'yicha aniqlanadi.",
        ]
        return PriceEstimateResult(
            area_m2=area_m2,
            design_key=design_key,
            design_title=title,
            rate_uzs_per_m2=rate,
            subtotal_uzs=subtotal,
            discount_percent=discount_pct,
            discount_amount_uzs=discount_amount,
            total_uzs=total,
            is_estimate=True,
            source="customer_facing",
            warnings=warnings,
        )

    def build_clarification(
        self,
        text: str,
    ) -> PriceClarificationResult:
        area = self.parse_area_from_text(text)
        design = self.parse_design_from_text(text)
        if area and design:
            return PriceClarificationResult(
                parsed_area=area, parsed_design=design,
            )
        if area and not design:
            return PriceClarificationResult(
                needs_design=True,
                parsed_area=area,
                question=(
                    "Qaysi potolok turi kerak?\n\n"
                    "Oddiy, Gulli, Hi-tech, Mramor, Naqsh, Kosmos, "
                    "Osmon yoki Qora UF"
                ),
            )
        if design and not area:
            return PriceClarificationResult(
                needs_area=True,
                parsed_design=design,
                question=(
                    "Xona razmerini yozing.\n\n"
                    "Masalan: 5x4 yoki 20 kv"
                ),
            )
        return PriceClarificationResult(
            needs_area=True,
            needs_design=True,
            question=(
                "Narx hisoblash uchun:\n"
                "1. Xona razmeri (masalan: 5x4 yoki 20 kv)\n"
                "2. Potolok turi (oddiy, gulli, hi-tech...)"
            ),
        )

    def build_user_response(self, result: PriceEstimateResult) -> str:
        lines = [
            "💰 <b>Taxminiy hisob:</b>",
            f"Maydon: {result.area_m2:g} m²",
            f"Tur: {result.design_title}",
            f"Narx: {self.format_uzs(result.rate_uzs_per_m2)} so'm/m²",
        ]
        if result.discount_percent > 0:
            lines.append(
                f"Chegirma: {result.discount_percent:g}% "
                f"(−{self.format_uzs(result.discount_amount_uzs)} so'm)",
            )
        lines.append(f"<b>Jami: {self.format_uzs(result.total_uzs)} so'm</b>")
        lines.append("")
        lines.append(
            "⚠️ Bu taxminiy hisob. Yakuniy narx o'lchov va "
            "material bo'yicha aniqlanadi.",
        )
        return "\n".join(lines)

    def build_memory_payload(
        self,
        result: PriceEstimateResult,
    ) -> dict[str, Any]:
        return {
            "last_price_area_m2": result.area_m2,
            "last_price_design": result.design_key,
            "last_price_total": result.total_uzs,
            "last_price_source": result.source,
            "last_price_is_estimate": result.is_estimate,
        }

    def extract_and_respond(self, text: str) -> PriceCalculatorResponse:
        clar = self.build_clarification(text)
        if clar.needs_area or clar.needs_design:
            return PriceCalculatorResponse(
                clarification=clar,
                user_text=clar.question,
            )
        assert clar.parsed_area is not None
        assert clar.parsed_design is not None
        est = self.calculate_estimate(clar.parsed_area, clar.parsed_design)
        return PriceCalculatorResponse(
            estimate=est,
            user_text=self.build_user_response(est),
            memory_payload=self.build_memory_payload(est),
        )

    @staticmethod
    def format_uzs(amount: int) -> str:
        return f"{amount:,}".replace(",", " ")

    @staticmethod
    def sanitize_price_text(text: str) -> str:
        return _TOKEN_RE.sub("[REDACTED]", text)

    @staticmethod
    def validate_area(area_m2: float) -> str | None:
        if area_m2 < MIN_AREA:
            return "Maydon juda kichik (kamida 1 m²)."
        if area_m2 > MAX_AREA:
            return "Maydon juda katta (maksimum 500 m²)."
        return None
