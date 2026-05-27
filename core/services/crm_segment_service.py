"""
core.services.crm_segment_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Contact segmentation. Pure functions.
"""

from __future__ import annotations

from typing import Any

_VALID_SEGMENTS = frozenset(
    {
        "hot_leads",
        "unanswered",
        "overdue",
        "critical_sla",
        "price_interested",
        "catalog_viewed",
        "phone_shared",
        "operator_requested",
        "order_started",
        "objection_price",
        "objection_trust",
        "inactive_3_days",
        "inactive_7_days",
        "stopped_users",
        "location_known",
        "area_known",
        "ceiling_type_known",
        "marketing_allowed",
    }
)

_NEXT_OFFERS: dict[str, str] = {
    "objection_price": "Arzonroq variant yoki to'lov rejasi taklif qiling",
    "area_known": "Narx hisoblab yuboring",
    "phone_shared": "Operatorga ulang — mijoz tayyor",
    "operator_requested": "Operator zudlik bilan bog'lansin",
    "price_interested": "Dizayn tanlashga yordam bering",
    "catalog_viewed": "Narx hisoblashni taklif qiling",
    "order_started": "Buyurtmani davom ettiring",
}


class CRMSegmentService:
    """Pure segment logic."""

    @staticmethod
    def is_valid_segment(name: str) -> bool:
        return name in _VALID_SEGMENTS

    @staticmethod
    def build_contact_segments(contact: dict[str, Any]) -> list[str]:
        segs: list[str] = []
        temp = contact.get("temperature")
        status = contact.get("lead_status", "")
        md = contact.get("metadata_json") or {}

        if temp == "hot":
            segs.append("hot_leads")
        if contact.get("phone"):
            segs.append("phone_shared")
        if status == "stopped":
            segs.append("stopped_users")
        if md.get("last_intent") == "wants_price" or status == "price_interested":
            segs.append("price_interested")
        if md.get("last_intent") == "wants_operator" or status == "operator_needed":
            segs.append("operator_requested")
        if md.get("last_intent") == "wants_order" or status == "order_started":
            segs.append("order_started")
        if md.get("objection_type") == "price":
            segs.append("objection_price")
        if md.get("objection_type") == "trust":
            segs.append("objection_trust")
        if contact.get("district") or md.get("district"):
            segs.append("location_known")
        if contact.get("area_m2") or md.get("area_m2"):
            segs.append("area_known")
        if contact.get("ceiling_type") or md.get("ceiling_type"):
            segs.append("ceiling_type_known")
        if CRMSegmentService.is_marketing_allowed(contact):
            segs.append("marketing_allowed")
        return segs

    @staticmethod
    def is_marketing_allowed(contact: dict[str, Any]) -> bool:
        if contact.get("lead_status") in ("stopped", "lost"):
            return False
        if contact.get("marketing_allowed") is False:
            return False
        if contact.get("followup_allowed") is False:
            return False
        md = contact.get("metadata_json") or {}
        if md.get("followup_disabled"):
            return False
        return True

    @staticmethod
    def build_next_best_offer(contact: dict[str, Any]) -> str | None:
        segs = CRMSegmentService.build_contact_segments(contact)
        for seg in (
            "operator_requested",
            "phone_shared",
            "objection_price",
            "area_known",
            "price_interested",
            "catalog_viewed",
            "order_started",
        ):
            if seg in segs and seg in _NEXT_OFFERS:
                return _NEXT_OFFERS[seg]
        return None
