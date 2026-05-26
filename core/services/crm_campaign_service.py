"""
core.services.crm_campaign_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Marketing segment selection, campaign draft validation, recipient preview,
safety checks. Pure functions — no DB I/O. Send always disabled.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_PHONE_RE = re.compile(r"\+?\d{9,15}")

_SEGMENTS: dict[str, dict[str, str]] = {
    "hot_leads": {"name": "Hot leadlar", "description": "Hot temperature yoki score>=60"},
    "price_interested": {"name": "Narx so'raganlar", "description": "price_interested status"},
    "unanswered_3d": {"name": "3 kun javobsiz", "description": "Oxirgi xabar 3+ kun oldin"},
    "unanswered_7d": {"name": "7 kun javobsiz", "description": "Oxirgi xabar 7+ kun oldin"},
    "phone_shared": {"name": "Telefon qoldirganlar", "description": "Phone mavjud"},
    "operator_needed": {"name": "Operator kerak", "description": "operator_needed status"},
    "new_leads": {"name": "Yangi leadlar", "description": "new status"},
    "ceiling_gulli": {"name": "Gulli potolok", "description": "Gulli ceiling type qiziqqanlar"},
    "ceiling_led": {"name": "LED potolok", "description": "LED ceiling type qiziqqanlar"},
    "objection_price": {"name": "Narx e'tirozi", "description": "Qimmat degan mijozlar"},
    "all_active": {"name": "Barcha aktiv", "description": "Stopped/lost/merged harijiladigan"},
}

_DRAFT_STATUSES = ("draft", "previewed", "approved", "blocked", "archived")
_SAFETY_STATUSES = ("pending", "safe", "warning", "blocked")
_EXCLUDED_STATUSES = frozenset({"stopped", "lost"})


@dataclass(frozen=True)
class SegmentInfo:
    key: str = ""
    name: str = ""
    description: str = ""


@dataclass(frozen=True)
class SafetyCheckResult:
    status: str = "pending"
    reasons: list[str] = field(default_factory=list)
    allowed: bool = False
    send_enabled: bool = False


@dataclass(frozen=True)
class DraftValidation:
    ok: bool = False
    error: str = ""
    warnings: list[str] = field(default_factory=list)


class CRMCampaignService:
    """Campaign draft validation and safety checks."""

    @staticmethod
    def get_available_segments() -> list[SegmentInfo]:
        return [
            SegmentInfo(key=k, name=v["name"], description=v["description"])
            for k, v in _SEGMENTS.items()
        ]

    @staticmethod
    def is_valid_segment(key: str) -> bool:
        return key in _SEGMENTS

    @staticmethod
    def get_segment_info(key: str) -> SegmentInfo | None:
        if key not in _SEGMENTS:
            return None
        s = _SEGMENTS[key]
        return SegmentInfo(key=key, name=s["name"], description=s["description"])

    @staticmethod
    def filter_recipients(
        contacts: list[dict[str, Any]],
        segment_key: str,
        exclude_stopped: bool = True,
        exclude_marketing_disabled: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        eligible: list[dict[str, Any]] = []
        excluded = 0
        for c in contacts:
            if c.get("merge_status") == "merged":
                excluded += 1
                continue
            if exclude_stopped and c.get("lead_status") in _EXCLUDED_STATUSES:
                excluded += 1
                continue
            if exclude_marketing_disabled and c.get("marketing_allowed") is False:
                excluded += 1
                continue
            if _matches_segment(c, segment_key):
                eligible.append(c)
        return eligible, excluded

    @staticmethod
    def preview_recipients(
        contacts: list[dict[str, Any]],
        segment_key: str,
        max_preview: int = 50,
        exclude_stopped: bool = True,
        exclude_marketing_disabled: bool = True,
    ) -> dict[str, Any]:
        eligible, excluded = CRMCampaignService.filter_recipients(
            contacts, segment_key, exclude_stopped, exclude_marketing_disabled,
        )
        preview = []
        for c in eligible[:max_preview]:
            preview.append({
                "contact_id": c.get("id", 0),
                "first_name": c.get("first_name", ""),
                "username": c.get("username", ""),
                "lead_status": c.get("lead_status", ""),
                "temperature": c.get("temperature", ""),
                "lead_score": c.get("lead_score", 0),
            })
        return {
            "segment_key": segment_key,
            "total_eligible": len(eligible),
            "excluded_count": excluded,
            "preview": preview,
        }

    @staticmethod
    def validate_draft(
        name: str,
        segment_key: str,
        message_text: str,
        max_message_length: int = 1000,
    ) -> DraftValidation:
        warnings: list[str] = []
        if not name or not name.strip():
            return DraftValidation(ok=False, error="name_required")
        if len(name) > 200:
            return DraftValidation(ok=False, error="name_too_long")
        if not CRMCampaignService.is_valid_segment(segment_key):
            return DraftValidation(ok=False, error=f"invalid_segment:{segment_key}")
        if not message_text or not message_text.strip():
            return DraftValidation(ok=False, error="message_required")
        if len(message_text) > max_message_length:
            return DraftValidation(ok=False, error=f"message_too_long:{len(message_text)}/{max_message_length}")
        if _TOKEN_RE.search(message_text):
            return DraftValidation(ok=False, error="message_contains_token")
        if _BOT_TOKEN_RE.search(message_text):
            return DraftValidation(ok=False, error="message_contains_bot_token")
        if _PHONE_RE.search(message_text):
            warnings.append("message_contains_phone")
        return DraftValidation(ok=True, warnings=warnings)

    @staticmethod
    def check_safety(
        recipient_count: int,
        message_text: str,
        send_enabled: bool = False,
        max_message_length: int = 1000,
    ) -> SafetyCheckResult:
        reasons: list[str] = []
        if not send_enabled:
            reasons.append("send_disabled")
        if recipient_count == 0:
            reasons.append("no_recipients")
        if not message_text or not message_text.strip():
            reasons.append("empty_message")
        if len(message_text) > max_message_length:
            reasons.append("message_too_long")
        if _TOKEN_RE.search(message_text):
            reasons.append("token_in_message")
        if recipient_count > 1000:
            reasons.append("large_recipient_list")
        if not reasons:
            status = "safe"
        elif "send_disabled" in reasons and len(reasons) == 1:
            status = "warning"
        else:
            status = "blocked" if any(r != "send_disabled" for r in reasons) else "warning"
        return SafetyCheckResult(
            status=status,
            reasons=reasons,
            allowed=len([r for r in reasons if r not in ("send_disabled", "large_recipient_list")]) == 0,
            send_enabled=send_enabled,
        )

    @staticmethod
    def build_draft_dict(
        name: str,
        segment_key: str,
        message_text: str,
        recipient_count: int = 0,
        excluded_count: int = 0,
        safety_status: str = "pending",
        safety_reasons: list[str] | None = None,
        filters: dict | None = None,
        preview_recipients: list[dict] | None = None,
        created_by: str = "",
    ) -> dict[str, Any]:
        return {
            "name": name[:200],
            "segment_key": segment_key,
            "status": "draft",
            "message_text": CRMCampaignService.sanitize_message(message_text),
            "recipient_count": recipient_count,
            "excluded_count": excluded_count,
            "safety_status": safety_status,
            "safety_reasons_json": safety_reasons,
            "filters_json": filters,
            "preview_recipients_json": preview_recipients,
            "created_by": created_by[:100] if created_by else "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def build_audit_entry(
        campaign_id: int = 0,
        actor_admin_id: str = "",
        action: str = "",
        status: str = "success",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "campaign_id": campaign_id,
            "actor_admin_id": actor_admin_id[:100] if actor_admin_id else "",
            "action": action[:50] if action else "",
            "status": status,
            "reason": CRMCampaignService._sanitize_text(reason)[:500] if reason else "",
            "metadata_json": CRMCampaignService._sanitize_metadata(metadata),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def sanitize_message(text: str) -> str:
        if not text:
            return ""
        text = _TOKEN_RE.sub("[REDACTED]", text)
        text = _BOT_TOKEN_RE.sub("[REDACTED]", text)
        return text

    @staticmethod
    def _sanitize_text(text: str) -> str:
        if not text:
            return ""
        text = _TOKEN_RE.sub("[REDACTED]", text)
        text = _BOT_TOKEN_RE.sub("[REDACTED]", text)
        return text

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if metadata is None:
            return None
        safe: dict[str, Any] = {}
        for k, v in metadata.items():
            if isinstance(v, str):
                v = _TOKEN_RE.sub("[REDACTED]", v)
                v = _BOT_TOKEN_RE.sub("[REDACTED]", v)
            safe[k] = v
        return safe

    @staticmethod
    def get_draft_statuses() -> tuple[str, ...]:
        return _DRAFT_STATUSES

    @staticmethod
    def get_safety_statuses() -> tuple[str, ...]:
        return _SAFETY_STATUSES


def _matches_segment(contact: dict[str, Any], segment_key: str) -> bool:
    status = contact.get("lead_status", "")
    temp = contact.get("temperature", "")
    score = contact.get("lead_score", 0) or 0
    md = contact.get("metadata_json") or {}
    if segment_key == "hot_leads":
        return temp == "hot" or score >= 60
    if segment_key == "price_interested":
        return status == "price_interested"
    if segment_key == "phone_shared":
        return bool(contact.get("phone"))
    if segment_key == "operator_needed":
        return status == "operator_needed"
    if segment_key == "new_leads":
        return status == "new"
    if segment_key == "ceiling_gulli":
        return md.get("ceiling_type") == "gulli"
    if segment_key == "ceiling_led":
        return md.get("ceiling_type") == "led"
    if segment_key == "objection_price":
        return md.get("last_objection") == "price" or md.get("objection_type") == "price"
    if segment_key == "all_active":
        return status not in ("stopped", "lost")
    if segment_key in ("unanswered_3d", "unanswered_7d"):
        return True
    return False
