"""
core.services.crm_campaign_send_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Campaign send validation, dry-run, limited send with canary. Pure functions.
No real Telegram calls — uses mockable sender protocol.
"""
from __future__ import annotations
import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_EXCLUDED_STATUSES = frozenset({"stopped", "lost"})


class TelegramCampaignSender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> int: ...


@dataclass(frozen=True)
class SendValidation:
    allowed: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecipientCheck:
    eligible: bool = True
    blocked_reason: str = ""
    is_canary: bool = False


@dataclass(frozen=True)
class DryRunResult:
    campaign_id: int = 0
    would_send: int = 0
    blocked: int = 0
    skipped: int = 0
    blockers_by_reason: dict[str, int] = field(default_factory=dict)
    sample_messages: list[str] = field(default_factory=list)
    dry_run: bool = True


@dataclass(frozen=True)
class SendResult:
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


class CRMCampaignSendService:
    """Campaign send validation and execution. Pure functions."""

    @staticmethod
    def validate_campaign_for_send(
        campaign: dict[str, Any],
        send_enabled: bool = False,
        dry_run_only: bool = True,
        require_approval: bool = True,
        confirm: bool = False,
        require_confirmation: bool = True,
        max_message_length: int = 1000,
    ) -> SendValidation:
        blockers: list[str] = []
        warnings: list[str] = []
        if not send_enabled:
            blockers.append("send_disabled")
        if dry_run_only:
            blockers.append("dry_run_only")
        if require_approval and campaign.get("status") != "approved":
            blockers.append("campaign_not_approved")
        if require_confirmation and not confirm:
            blockers.append("confirmation_required")
        msg = campaign.get("message_text", "")
        if not msg or not msg.strip():
            blockers.append("empty_message")
        if len(msg) > max_message_length:
            blockers.append("message_too_long")
        if _TOKEN_RE.search(msg):
            blockers.append("token_in_message")
        if _BOT_TOKEN_RE.search(msg):
            blockers.append("bot_token_in_message")
        return SendValidation(
            allowed=len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
        )

    @staticmethod
    def validate_recipient(
        contact: dict[str, Any],
        canary_enabled: bool = False,
        canary_ids: set[int] | None = None,
        already_sent_ids: set[int] | None = None,
    ) -> RecipientCheck:
        cid = contact.get("id", 0)
        if contact.get("merge_status") == "merged":
            return RecipientCheck(eligible=False, blocked_reason="merged")
        if contact.get("lead_status") in _EXCLUDED_STATUSES:
            return RecipientCheck(eligible=False, blocked_reason=f"status_{contact.get('lead_status')}")
        if contact.get("marketing_allowed") is False:
            return RecipientCheck(eligible=False, blocked_reason="marketing_disabled")
        if contact.get("followup_allowed") is False:
            return RecipientCheck(eligible=False, blocked_reason="followup_disabled")
        md = contact.get("metadata_json") or {}
        if md.get("stop_request") or md.get("opted_out"):
            return RecipientCheck(eligible=False, blocked_reason="opted_out")
        if not contact.get("telegram_chat_id") and not contact.get("telegram_user_id"):
            return RecipientCheck(eligible=False, blocked_reason="no_telegram_id")
        if already_sent_ids and cid in already_sent_ids:
            return RecipientCheck(eligible=False, blocked_reason="duplicate_send")
        is_canary = canary_ids is not None and cid in canary_ids
        if canary_enabled and canary_ids and cid not in canary_ids:
            return RecipientCheck(eligible=False, blocked_reason="not_in_canary", is_canary=False)
        return RecipientCheck(eligible=True, is_canary=is_canary)

    @staticmethod
    def revalidate_message_safety(message_text: str) -> SendValidation:
        blockers: list[str] = []
        if _TOKEN_RE.search(message_text):
            blockers.append("token_in_message")
        if _BOT_TOKEN_RE.search(message_text):
            blockers.append("bot_token_in_message")
        if not message_text.strip():
            blockers.append("empty_message")
        return SendValidation(allowed=len(blockers) == 0, blockers=blockers)

    @staticmethod
    def build_personalized_message(
        template: str,
        contact: dict[str, Any],
    ) -> str:
        md = contact.get("metadata_json") or {}
        replacements = {
            "{first_name}": contact.get("first_name") or "",
            "{username}": contact.get("username") or "",
            "{ceiling_type}": md.get("ceiling_type") or "",
            "{area_m2}": str(md.get("area_m2") or ""),
            "{district}": md.get("district") or "",
        }
        result = template
        for key, val in replacements.items():
            result = result.replace(key, val)
        return result

    @staticmethod
    def dry_run(
        campaign: dict[str, Any],
        contacts: list[dict[str, Any]],
        max_recipients: int = 10,
        canary_enabled: bool = False,
        canary_ids: set[int] | None = None,
    ) -> DryRunResult:
        would_send = 0
        blocked = 0
        skipped = 0
        blockers_by_reason: dict[str, int] = {}
        sample_messages: list[str] = []
        msg_template = campaign.get("message_text", "")
        for c in contacts[:max_recipients * 3]:
            check = CRMCampaignSendService.validate_recipient(
                c, canary_enabled=canary_enabled, canary_ids=canary_ids,
            )
            if not check.eligible:
                blocked += 1
                reason = check.blocked_reason
                blockers_by_reason[reason] = blockers_by_reason.get(reason, 0) + 1
                continue
            if would_send >= max_recipients:
                skipped += 1
                continue
            would_send += 1
            if len(sample_messages) < 3:
                sample_messages.append(
                    CRMCampaignSendService.build_personalized_message(msg_template, c)[:200]
                )
        return DryRunResult(
            campaign_id=campaign.get("id", 0),
            would_send=would_send,
            blocked=blocked,
            skipped=skipped,
            blockers_by_reason=blockers_by_reason,
            sample_messages=sample_messages,
        )

    @staticmethod
    def build_batch_id() -> str:
        return f"batch_{secrets.token_hex(8)}"

    @staticmethod
    def build_send_attempt(
        campaign_id: int,
        contact_id: int,
        telegram_user_id: int | None = None,
        status: str = "proposed",
        message_preview: str = "",
        blocked_reason: str = "",
        batch_id: str = "",
    ) -> dict[str, Any]:
        return {
            "campaign_id": campaign_id,
            "contact_id": contact_id,
            "telegram_user_id": telegram_user_id,
            "status": status,
            "message_preview": message_preview[:200] if message_preview else "",
            "blocked_reason": blocked_reason[:200] if blocked_reason else "",
            "message_hash": hashlib.sha256(message_preview.encode()).hexdigest()[:16] if message_preview else "",
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def mark_attempt_sent(telegram_message_id: int | None = None) -> dict[str, Any]:
        return {
            "status": "sent",
            "telegram_message_id": telegram_message_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def mark_attempt_failed(error: str = "") -> dict[str, Any]:
        return {
            "status": "failed",
            "error_message": CRMCampaignSendService.redact_error(error),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def mark_attempt_blocked(reason: str = "") -> dict[str, Any]:
        return {"status": "blocked", "blocked_reason": reason[:200]}

    @staticmethod
    def sanitize_send_result(result: dict[str, Any]) -> dict[str, Any]:
        safe = dict(result)
        safe.pop("telegram_chat_id_hash", None)
        for key in list(safe.keys()):
            val = safe[key]
            if isinstance(val, str) and _TOKEN_RE.search(val):
                safe[key] = "[REDACTED]"
        return safe

    @staticmethod
    def redact_error(error: str) -> str:
        if not error:
            return ""
        error = _TOKEN_RE.sub("[REDACTED]", error)
        error = _BOT_TOKEN_RE.sub("[REDACTED]", error)
        return error[:500]
