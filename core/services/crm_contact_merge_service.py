"""
core.services.crm_contact_merge_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Duplicate detection, merge preview/plan, data quality. Pure functions.
Actual merge is feature-flag gated (CRM_CONTACT_MERGE_ENABLED).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d{9,15}")

_STATUS_PRIORITY = {
    "hot": 1, "operator_needed": 2, "price_interested": 3, "order_started": 4,
    "active": 5, "browsing": 6, "new": 7, "won": 8, "lost": 9, "stopped": 10,
}
_TEMP_PRIORITY = {"hot": 1, "warm": 2, "cold": 3}


@dataclass(frozen=True)
class DuplicateCandidate:
    contact_a_id: int = 0
    contact_b_id: int = 0
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MergePreview:
    source_id: int = 0
    target_id: int = 0
    confidence: int = 0
    reasons: list[str] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    allowed: bool = False


@dataclass(frozen=True)
class MergeResult:
    ok: bool = False
    source_id: int = 0
    target_id: int = 0
    error: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DataQualitySummary:
    total_contacts: int = 0
    active_contacts: int = 0
    merged_contacts: int = 0
    duplicate_candidates: int = 0
    missing_phone: int = 0
    missing_name: int = 0
    missing_location: int = 0
    missing_area: int = 0
    avg_quality_score: float = 0.0


class CRMContactMergeService:
    """Duplicate detection and merge operations. Pure functions."""

    @staticmethod
    def calculate_duplicate_confidence(
        contact_a: dict[str, Any],
        contact_b: dict[str, Any],
    ) -> int:
        if contact_a.get("id") == contact_b.get("id"):
            return 0
        if _is_merged(contact_a) or _is_merged(contact_b):
            return 0
        tg_a = contact_a.get("telegram_user_id")
        tg_b = contact_b.get("telegram_user_id")
        if tg_a and tg_b and tg_a == tg_b:
            return 100
        chat_a = contact_a.get("telegram_chat_id")
        chat_b = contact_b.get("telegram_chat_id")
        if chat_a and chat_b and chat_a == chat_b:
            return 95
        phone_a = _normalize_phone(contact_a.get("phone", ""))
        phone_b = _normalize_phone(contact_b.get("phone", ""))
        if phone_a and phone_b and phone_a == phone_b:
            return 95
        if phone_a and phone_b and len(phone_a) >= 9 and len(phone_b) >= 9 and phone_a[-9:] == phone_b[-9:]:
            return 85
        user_a = (contact_a.get("username") or "").lower().strip()
        user_b = (contact_b.get("username") or "").lower().strip()
        name_a = (contact_a.get("first_name") or "").lower().strip()
        name_b = (contact_b.get("first_name") or "").lower().strip()
        if user_a and user_b and user_a == user_b:
            if name_a and name_b and name_a == name_b:
                return 80
            return 60
        if name_a and name_b and name_a == name_b and not phone_a and not phone_b:
            return 30
        return 0

    @staticmethod
    def build_duplicate_reasons(
        contact_a: dict[str, Any],
        contact_b: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        tg_a = contact_a.get("telegram_user_id")
        tg_b = contact_b.get("telegram_user_id")
        if tg_a and tg_b and tg_a == tg_b:
            reasons.append("same_telegram_user_id")
        chat_a = contact_a.get("telegram_chat_id")
        chat_b = contact_b.get("telegram_chat_id")
        if chat_a and chat_b and chat_a == chat_b:
            reasons.append("same_telegram_chat_id")
        phone_a = _normalize_phone(contact_a.get("phone", ""))
        phone_b = _normalize_phone(contact_b.get("phone", ""))
        if phone_a and phone_b:
            if phone_a == phone_b:
                reasons.append("same_phone")
            elif len(phone_a) >= 9 and len(phone_b) >= 9 and phone_a[-9:] == phone_b[-9:]:
                reasons.append("same_phone_last_9")
        user_a = (contact_a.get("username") or "").lower().strip()
        user_b = (contact_b.get("username") or "").lower().strip()
        if user_a and user_b and user_a == user_b:
            reasons.append("same_username")
        name_a = (contact_a.get("first_name") or "").lower().strip()
        name_b = (contact_b.get("first_name") or "").lower().strip()
        if name_a and name_b and name_a == name_b:
            reasons.append("same_first_name")
        return reasons

    @staticmethod
    def find_duplicate_candidates(
        contacts: list[dict[str, Any]],
        min_confidence: int = 60,
        limit: int = 100,
    ) -> list[DuplicateCandidate]:
        candidates: list[DuplicateCandidate] = []
        seen: set[tuple[int, int]] = set()
        for i, a in enumerate(contacts):
            if _is_merged(a):
                continue
            for b in contacts[i + 1:]:
                if _is_merged(b):
                    continue
                pair = (min(a.get("id", 0), b.get("id", 0)), max(a.get("id", 0), b.get("id", 0)))
                if pair in seen:
                    continue
                conf = CRMContactMergeService.calculate_duplicate_confidence(a, b)
                if conf >= min_confidence:
                    reasons = CRMContactMergeService.build_duplicate_reasons(a, b)
                    candidates.append(DuplicateCandidate(
                        contact_a_id=a.get("id", 0),
                        contact_b_id=b.get("id", 0),
                        confidence=conf,
                        reasons=reasons,
                    ))
                    seen.add(pair)
                    if len(candidates) >= limit:
                        return candidates
        return candidates

    @staticmethod
    def build_merge_plan(
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "keep_phone": _choose_best(target.get("phone"), source.get("phone")),
            "keep_name": _choose_best(target.get("first_name"), source.get("first_name")),
            "keep_username": _choose_best(target.get("username"), source.get("username")),
            "keep_telegram_user_id": target.get("telegram_user_id") or source.get("telegram_user_id"),
            "keep_telegram_chat_id": target.get("telegram_chat_id") or source.get("telegram_chat_id"),
            "keep_score": max(target.get("lead_score", 0) or 0, source.get("lead_score", 0) or 0),
            "keep_temperature": _choose_hottest(target.get("temperature"), source.get("temperature")),
            "keep_status": _choose_priority_status(target.get("lead_status"), source.get("lead_status")),
            "merge_tags": True,
            "merge_notes": True,
            "merge_messages": True,
            "merge_tasks": True,
            "source_action": "soft_mark",
        }

    @staticmethod
    def build_merge_preview(
        source: dict[str, Any],
        target: dict[str, Any],
        merge_enabled: bool = False,
        min_confidence: int = 80,
        require_confirmation: bool = True,
    ) -> MergePreview:
        confidence = CRMContactMergeService.calculate_duplicate_confidence(source, target)
        reasons = CRMContactMergeService.build_duplicate_reasons(source, target)
        plan = CRMContactMergeService.build_merge_plan(source, target)
        blockers: list[str] = []
        warnings: list[str] = []
        if source.get("id") == target.get("id"):
            blockers.append("source_equals_target")
        if _is_merged(source):
            blockers.append("source_already_merged")
        if _is_merged(target):
            blockers.append("target_already_merged")
        tg_a = source.get("telegram_user_id")
        tg_b = target.get("telegram_user_id")
        if tg_a and tg_b and tg_a != tg_b:
            blockers.append("different_telegram_user_ids")
        phone_a = _normalize_phone(source.get("phone", ""))
        phone_b = _normalize_phone(target.get("phone", ""))
        if phone_a and phone_b and phone_a != phone_b and phone_a[-9:] != phone_b[-9:]:
            blockers.append("different_phones_no_match")
        if confidence < min_confidence:
            blockers.append(f"low_confidence:{confidence}<{min_confidence}")
        if not merge_enabled:
            warnings.append("merge_disabled_preview_only")
        if source.get("lead_status") in ("stopped", "lost", "won"):
            warnings.append("source_terminal_status")
        return MergePreview(
            source_id=source.get("id", 0),
            target_id=target.get("id", 0),
            confidence=confidence,
            reasons=reasons,
            plan=plan,
            warnings=warnings,
            blockers=blockers,
            allowed=len(blockers) == 0,
        )

    @staticmethod
    def validate_merge(
        source: dict[str, Any],
        target: dict[str, Any],
        merge_enabled: bool = False,
        confirm: bool = False,
        require_confirmation: bool = True,
        min_confidence: int = 80,
    ) -> MergeResult:
        if not merge_enabled:
            return MergeResult(ok=False, error="merge_disabled")
        if require_confirmation and not confirm:
            return MergeResult(ok=False, error="confirmation_required")
        preview = CRMContactMergeService.build_merge_preview(
            source, target, merge_enabled=True, min_confidence=min_confidence,
        )
        if not preview.allowed:
            return MergeResult(ok=False, error="; ".join(preview.blockers))
        return MergeResult(
            ok=True,
            source_id=source.get("id", 0),
            target_id=target.get("id", 0),
            warnings=preview.warnings,
        )

    @staticmethod
    def build_source_merged_dict(target_contact_id: int) -> dict[str, Any]:
        return {
            "merged_into_contact_id": target_contact_id,
            "merged_at": datetime.now(UTC).isoformat(),
            "merge_status": "merged",
        }

    @staticmethod
    def build_merge_audit(
        source_id: int,
        target_id: int,
        actor_admin_id: str = "",
        status: str = "previewed",
        confidence: int = 0,
        reasons: list[str] | None = None,
        plan: dict[str, Any] | None = None,
        source_snapshot: dict[str, Any] | None = None,
        target_snapshot: dict[str, Any] | None = None,
        error: str = "",
    ) -> dict[str, Any]:
        return {
            "source_contact_id": source_id,
            "target_contact_id": target_id,
            "actor_admin_id": actor_admin_id[:100] if actor_admin_id else "",
            "status": status,
            "confidence": confidence,
            "reasons_json": reasons,
            "merge_plan_json": plan,
            "before_source_json": CRMContactMergeService.sanitize_snapshot(source_snapshot),
            "before_target_json": CRMContactMergeService.sanitize_snapshot(target_snapshot),
            "error_message": error[:500] if error else None,
            "created_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def build_data_quality_summary(contacts: list[dict[str, Any]]) -> DataQualitySummary:
        if not contacts:
            return DataQualitySummary()
        total = len(contacts)
        active = sum(1 for c in contacts if c.get("merge_status", "active") == "active")
        merged = sum(1 for c in contacts if c.get("merge_status") == "merged")
        missing_phone = sum(1 for c in contacts if not c.get("phone") and c.get("merge_status", "active") == "active")
        missing_name = sum(1 for c in contacts if not c.get("first_name") and c.get("merge_status", "active") == "active")
        missing_loc = sum(1 for c in contacts if not (c.get("metadata_json") or {}).get("district") and c.get("merge_status", "active") == "active")
        missing_area = sum(1 for c in contacts if not (c.get("metadata_json") or {}).get("area_m2") and c.get("merge_status", "active") == "active")
        scores = [c.get("data_quality_score", 0) or 0 for c in contacts if c.get("merge_status", "active") == "active"]
        avg = sum(scores) / len(scores) if scores else 0.0
        return DataQualitySummary(
            total_contacts=total, active_contacts=active, merged_contacts=merged,
            missing_phone=missing_phone, missing_name=missing_name,
            missing_location=missing_loc, missing_area=missing_area,
            avg_quality_score=round(avg, 1),
        )

    @staticmethod
    def sanitize_snapshot(contact: dict[str, Any] | None) -> dict[str, Any] | None:
        if contact is None:
            return None
        safe = dict(contact)
        safe.pop("session_id_hash", None)
        for key in list(safe.keys()):
            val = safe[key]
            if isinstance(val, str) and _TOKEN_RE.search(val):
                safe[key] = "[REDACTED]"
        if safe.get("phone"):
            phone = safe["phone"]
            if len(phone) > 4:
                safe["phone"] = phone[:4] + "*" * (len(phone) - 4)
        return safe

    @staticmethod
    def choose_best_field(target_val: Any, source_val: Any) -> Any:
        return _choose_best(target_val, source_val)


def _normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    return re.sub(r"\D", "", phone)


def _is_merged(contact: dict[str, Any]) -> bool:
    return contact.get("merge_status") == "merged"


def _choose_best(target_val: Any, source_val: Any) -> Any:
    if target_val:
        return target_val
    return source_val


def _choose_hottest(a: str | None, b: str | None) -> str:
    pa = _TEMP_PRIORITY.get(a or "", 99)
    pb = _TEMP_PRIORITY.get(b or "", 99)
    return a if pa <= pb else (b or a or "")


def _choose_priority_status(a: str | None, b: str | None) -> str:
    pa = _STATUS_PRIORITY.get(a or "", 99)
    pb = _STATUS_PRIORITY.get(b or "", 99)
    return a if pa <= pb else (b or a or "")
