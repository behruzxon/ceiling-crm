"""Frozen dataclasses for CRM campaign send schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CRMCampaignSendPreview:
    campaign_id: int = 0
    total_recipients: int = 0
    canary_recipients: int = 0
    excluded_count: int = 0
    dry_run: bool = True
    send_enabled: bool = False
    recipients: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class CRMCampaignSendRecipient:
    contact_id: int = 0
    first_name: str = ""
    username: str = ""
    is_canary: bool = False
    eligible: bool = True
    blocked_reason: str = ""


@dataclass(frozen=True)
class CRMCampaignSendRequest:
    campaign_id: int = 0
    confirm: bool = False
    dry_run: bool = True
    canary_only: bool = True
    batch_limit: int = 5


@dataclass(frozen=True)
class CRMCampaignSendResult:
    ok: bool = False
    campaign_id: int = 0
    proposed: int = 0
    sent: int = 0
    skipped: int = 0
    blocked: int = 0
    failed: int = 0
    dry_run: bool = True
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    batch_id: str = ""


@dataclass(frozen=True)
class CRMCampaignSendAttemptRecord:
    id: int = 0
    campaign_id: int = 0
    contact_id: int = 0
    status: str = ""
    message_preview: str = ""
    blocked_reason: str = ""
    batch_id: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class CRMCampaignSendSafetyResult:
    allowed: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
