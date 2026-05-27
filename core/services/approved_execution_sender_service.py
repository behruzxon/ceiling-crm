"""
core.services.approved_execution_sender_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Sends admin-approved agent execution payloads via Telegram bot.
Revalidates safety before every send.  Mockable bot interface.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Protocol

from core.schemas.agent_execution import AgentExecutionResult
from infrastructure.database.models.agent_execution_record import (
    AgentExecutionRecordModel,
)
from shared.constants.enums import AgentExecutionStatus
from shared.logging import get_logger

log = get_logger(__name__)

_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_FAKE_DISCOUNT_RE = re.compile(r"\d+\s*%")
_SAME_DAY_RE = re.compile(r"bugun qilamiz", re.IGNORECASE)
_ENG_ARZON_RE = re.compile(r"eng arzon", re.IGNORECASE)

_SENDABLE_ACTIONS: frozenset[str] = frozenset(
    {
        "send_user_reply",
        "send_admin_alert",
        "handoff_operator",
    }
)


class BotSender(Protocol):
    async def send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs: Any,
    ) -> Any: ...


class ApprovedExecutionSenderService:
    """Sends approved execution payloads via bot."""

    @staticmethod
    def validate_before_send(
        record: AgentExecutionRecordModel,
        now: datetime | None = None,
    ) -> AgentExecutionResult:
        if now is None:
            now = datetime.now(UTC)

        if record.status != AgentExecutionStatus.APPROVED.value:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason=f"invalid_status:{record.status}",
                mode=record.mode,
                status=record.status,
            )

        if record.executed_at is not None:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason="already_executed",
                mode=record.mode,
                status=record.status,
            )

        if record.failed_at is not None:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason="previously_failed",
                mode=record.mode,
                status=record.status,
            )

        if record.expires_at < now:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason="expired",
                mode=record.mode,
                status=record.status,
            )

        payload = record.payload_json or {}
        action = record.action
        msg = payload.get("message_text", "")

        if action not in _SENDABLE_ACTIONS:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason=f"unsendable_action:{action}",
                mode=record.mode,
                status=record.status,
            )

        if action in ("send_user_reply", "handoff_operator"):
            if not record.telegram_user_id:
                return AgentExecutionResult(
                    would_execute=False,
                    blocked=True,
                    blocked_reason="missing_target_user",
                    mode=record.mode,
                    status=record.status,
                )
            if not msg or not msg.strip():
                return AgentExecutionResult(
                    would_execute=False,
                    blocked=True,
                    blocked_reason="empty_message",
                    mode=record.mode,
                    status=record.status,
                )

        blocked, reason = ApprovedExecutionSenderService._check_message_safety(msg)
        if blocked:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason=reason,
                mode=record.mode,
                status=record.status,
            )

        risk = record.risk_level
        channel = record.channel or ""
        if risk in ("high", "critical") and channel == "user_dm":
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason="high_risk_user_dm",
                mode=record.mode,
                status=record.status,
            )

        return AgentExecutionResult(
            would_execute=True,
            blocked=False,
            mode=record.mode,
            status=record.status,
            safe_to_execute=True,
        )

    @staticmethod
    async def send_record(
        record: AgentExecutionRecordModel,
        bot: BotSender,
        admin_chat_id: int | None = None,
    ) -> AgentExecutionResult:
        validation = ApprovedExecutionSenderService.validate_before_send(record)
        if validation.blocked:
            return validation

        payload = record.payload_json or {}
        action = record.action
        msg = payload.get("message_text", "")

        try:
            if action in ("send_user_reply", "handoff_operator"):
                await bot.send_message(
                    chat_id=record.telegram_user_id,
                    text=msg,
                )
            elif action == "send_admin_alert":
                alert = payload.get("admin_alert_text", msg)
                target = admin_chat_id or record.telegram_user_id
                if target:
                    await bot.send_message(chat_id=target, text=alert)

            return AgentExecutionResult(
                would_execute=True,
                blocked=False,
                mode=record.mode,
                status=AgentExecutionStatus.EXECUTED.value,
                safe_to_execute=True,
            )
        except Exception as exc:
            error_msg = str(exc)[:200]
            if _TOKEN_RE.search(error_msg):
                error_msg = "send_error_redacted"
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason=f"send_failed:{error_msg}",
                mode=record.mode,
                status=AgentExecutionStatus.FAILED.value,
            )

    @staticmethod
    async def process_approved(
        records: list[AgentExecutionRecordModel],
        bot: BotSender,
        admin_chat_id: int | None = None,
        mark_failed_on_error: bool = True,
    ) -> list[tuple[str, AgentExecutionResult]]:
        results: list[tuple[str, AgentExecutionResult]] = []
        for record in records:
            validation = ApprovedExecutionSenderService.validate_before_send(
                record,
            )
            if validation.blocked:
                results.append((record.execution_id, validation))
                continue

            result = await ApprovedExecutionSenderService.send_record(
                record,
                bot,
                admin_chat_id,
            )
            results.append((record.execution_id, result))
        return results

    @staticmethod
    def build_safe_send_payload(
        record: AgentExecutionRecordModel,
    ) -> dict[str, Any]:
        payload = dict(record.payload_json or {})
        for key in ("message_text", "admin_alert_text"):
            val = payload.get(key)
            if isinstance(val, str):
                val = _PHONE_RE.sub("[***]", val)
                val = _TOKEN_RE.sub("[REDACTED]", val)
                payload[key] = val
        return payload

    @staticmethod
    def sanitize_error(error: str) -> str:
        error = _TOKEN_RE.sub("[REDACTED]", error)
        error = _PHONE_RE.sub("[***]", error)
        return error[:500]

    @staticmethod
    def _check_message_safety(msg: str) -> tuple[bool, str | None]:
        if not msg:
            return False, None
        if _TOKEN_RE.search(msg):
            return True, "token_in_message"
        if _PHONE_RE.search(msg):
            return True, "raw_phone_in_message"
        if _FAKE_DISCOUNT_RE.search(msg):
            return True, "fake_discount"
        if _SAME_DAY_RE.search(msg):
            return True, "same_day_promise"
        if _ENG_ARZON_RE.search(msg):
            return True, "eng_arzon_claim"
        return False, None
