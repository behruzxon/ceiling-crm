"""Frozen dataclasses for CRM campaign schemas."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CRMMarketingSegment:
    key: str = ""
    name: str = ""
    description: str = ""
    estimated_count: int = 0


@dataclass(frozen=True)
class CRMRecipientPreview:
    contact_id: int = 0
    first_name: str = ""
    username: str = ""
    lead_status: str = ""
    temperature: str = ""
    lead_score: int = 0


@dataclass(frozen=True)
class CRMCampaignDraftCreate:
    name: str = ""
    segment_key: str = ""
    message_text: str = ""
    filters_json: dict | None = None
    created_by: str = ""


@dataclass(frozen=True)
class CRMCampaignDraftUpdate:
    name: str | None = None
    message_text: str | None = None
    filters_json: dict | None = None
    updated_by: str = ""


@dataclass(frozen=True)
class CRMCampaignDraftResponse:
    id: int = 0
    name: str = ""
    segment_key: str = ""
    status: str = "draft"
    message_text: str = ""
    recipient_count: int = 0
    excluded_count: int = 0
    safety_status: str = "pending"
    safety_reasons: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class CRMCampaignSafetyResult:
    status: str = "pending"
    reasons: list[str] = field(default_factory=list)
    allowed: bool = False
    send_enabled: bool = False


@dataclass(frozen=True)
class CRMCampaignAuditItem:
    campaign_id: int = 0
    actor_admin_id: str = ""
    action: str = ""
    status: str = "success"
    reason: str = ""
    created_at: str = ""
