"""Frozen dataclasses for CRM contact merge schemas."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CRMDuplicateCandidate:
    contact_a_id: int = 0
    contact_b_id: int = 0
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CRMDuplicateDetectionResult:
    candidates: list[CRMDuplicateCandidate] = field(default_factory=list)
    total_contacts_scanned: int = 0
    duplicates_found: int = 0


@dataclass(frozen=True)
class CRMContactMergePreview:
    source_id: int = 0
    target_id: int = 0
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)
    merge_plan: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    allowed: bool = False


@dataclass(frozen=True)
class CRMContactMergePlan:
    keep_phone: str = ""
    keep_name: str = ""
    keep_status: str = ""
    keep_temperature: str = ""
    keep_score: int = 0
    merge_tags: bool = True
    merge_notes: bool = True
    merge_messages: bool = True
    source_action: str = "soft_mark"


@dataclass(frozen=True)
class CRMContactMergeResult:
    ok: bool = False
    source_id: int = 0
    target_id: int = 0
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CRMContactMergeAuditItem:
    source_contact_id: int = 0
    target_contact_id: int = 0
    actor_admin_id: str = ""
    status: str = ""
    confidence: int = 0
    created_at: str = ""


@dataclass(frozen=True)
class CRMDataQualitySummary:
    total_contacts: int = 0
    active_contacts: int = 0
    merged_contacts: int = 0
    duplicate_candidates: int = 0
    missing_phone: int = 0
    missing_name: int = 0
    avg_quality_score: float = 0.0
