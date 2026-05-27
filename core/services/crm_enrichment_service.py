"""
core.services.crm_enrichment_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic customer data extraction from text. Pure functions.
"""

from __future__ import annotations

import re
from typing import Any

from shared.utils.area_parser import parse_area

_PHONE_RE = re.compile(r"(?:\+?998|0)?(\d{9})")
_BUDGET_RE = re.compile(r"(\d+)\s*(?:mln|million|млн|ming|тыс|минг)", re.IGNORECASE)

_CEILING_TYPES: dict[str, str] = {
    "gulli": "gulli",
    "pechat": "pechat",
    "matoviy": "matoviy",
    "glossy": "glossy",
    "led": "led",
    "yulduz": "yulduzli",
    "mramor": "mramor",
    "oddiy": "oddiy",
    "satin": "satin",
    "hi-tech": "hi_tech",
    "osmon": "osmon",
    "kosmos": "kosmos",
}

_LOCATIONS: tuple[str, ...] = (
    "qarshi",
    "shahrisabz",
    "yakkabog'",
    "kitob",
    "qamashi",
    "kasbi",
    "muborak",
    "g'uzor",
    "nishon",
    "koson",
    "chiroqchi",
    "dehqonobod",
    "mirishkor",
    "toshkent",
    "samarqand",
    "buxoro",
    "navoiy",
    "urganch",
)

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


class CRMEnrichmentService:
    """Deterministic customer data extraction."""

    @staticmethod
    def extract_phone(text: str) -> str | None:
        m = _PHONE_RE.search(text)
        if m:
            digits = m.group(1)
            if len(digits) == 9:
                return f"+998{digits}"
        return None

    @staticmethod
    def extract_area_m2(text: str) -> float | None:
        return parse_area(text)

    @staticmethod
    def extract_ceiling_type(text: str) -> str | None:
        t = text.lower()
        for kw, val in _CEILING_TYPES.items():
            if kw in t:
                return val
        return None

    @staticmethod
    def extract_location(text: str) -> str | None:
        t = text.lower()
        for loc in _LOCATIONS:
            if loc in t:
                return loc
        return None

    @staticmethod
    def extract_budget_hint(text: str) -> str | None:
        m = _BUDGET_RE.search(text)
        if m:
            return f"{m.group(0)}"
        if "arzon" in text.lower():
            return "arzon"
        if "qimmat" in text.lower():
            return "qimmat"
        return None

    @staticmethod
    def enrich_from_text(text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        phone = CRMEnrichmentService.extract_phone(text)
        if phone:
            result["phone"] = phone
        area = CRMEnrichmentService.extract_area_m2(text)
        if area:
            result["area_m2"] = area
        ceiling = CRMEnrichmentService.extract_ceiling_type(text)
        if ceiling:
            result["ceiling_type"] = ceiling
        location = CRMEnrichmentService.extract_location(text)
        if location:
            result["district"] = location
        budget = CRMEnrichmentService.extract_budget_hint(text)
        if budget:
            result["budget_text"] = budget
        return result

    @staticmethod
    def enrich_from_signal(signal: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if signal.get("intent"):
            result["last_intent"] = signal["intent"]
        if signal.get("objection_type"):
            result["objection_type"] = signal["objection_type"]
        if signal.get("urgency"):
            result["urgency"] = signal["urgency"]
        if signal.get("area_m2"):
            result["area_m2"] = signal["area_m2"]
        return result

    @staticmethod
    def should_disable_marketing(signal: dict[str, Any]) -> bool:
        return signal.get("intent") == "stop_request"
