"""Operator handoff queue service — safe, no-ETA, dedup-aware."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class HandoffResult:
    handoff_id: int | None = None
    status: str = "open"
    priority: str = "normal"
    is_duplicate: bool = False
    user_message: str = ""


VALID_STATUSES = frozenset(
    {
        "open",
        "waiting_phone",
        "assigned",
        "contacted",
        "resolved",
        "cancelled",
        "expired",
    }
)
VALID_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
VALID_SOURCES = frozenset(
    {
        "ai_button",
        "text_intent",
        "operator_button",
        "crm_manual",
    }
)

_TOKEN_PATTERN = re.compile(r"(sk-[a-zA-Z0-9]{8,}|Bearer\s+\S{10,})", re.I)
_PHONE_PATTERN = re.compile(r"\+?\d{10,}")

DEFAULT_DEDUP_MINUTES = 30
DEFAULT_EXPIRE_HOURS = 24
DEFAULT_URGENT_SCORE_THRESHOLD = 80


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 6:
        return phone
    return phone[:4] + "****" + phone[-2:]


def sanitize_message_preview(text: str | None, max_len: int = 200) -> str | None:
    if not text:
        return None
    cleaned = _TOKEN_PATTERN.sub("[REDACTED]", text)
    return cleaned[:max_len]


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    result = {}
    for key, val in metadata.items():
        if isinstance(val, str):
            val = _TOKEN_PATTERN.sub("[REDACTED]", val)
        result[key] = val
    return result


def calculate_priority(
    *,
    lead_score: int = 0,
    reason: str | None = None,
    has_phone: bool = False,
    is_repeated: bool = False,
    urgent_threshold: int = DEFAULT_URGENT_SCORE_THRESHOLD,
) -> str:
    if lead_score >= urgent_threshold:
        return "urgent"
    if reason in ("complaint", "angry_objection"):
        return "urgent"
    if is_repeated and lead_score >= 60:
        return "urgent"
    if has_phone and reason in ("price_question", "measurement_request"):
        return "high"
    if reason == "measurement_request":
        return "high"
    if has_phone and lead_score >= 40:
        return "high"
    return "normal"


def build_user_message(*, has_phone: bool, is_duplicate: bool = False) -> str:
    if is_duplicate:
        return (
            "👨‍💼 So'rovingiz operatorga yuborilgan. "
            "Qo'shimcha savolingiz bo'lsa shu yerga yozing."
        )
    if has_phone:
        return (
            "👨‍💼 Operatorga ulash uchun so'rovingiz qabul qilindi. "
            "Operator xabaringizni ko'rib chiqadi."
        )
    return (
        "👨‍💼 Operatorga ulash uchun so'rovingiz qabul qilindi. "
        "Sizga bog'lanishimiz uchun telefon raqamingizni yuboring."
    )


@dataclass
class QueueSummary:
    total_open: int = 0
    total_waiting_phone: int = 0
    total_assigned: int = 0
    total_urgent: int = 0
    total_high: int = 0


EXPIRABLE_STATUSES = frozenset({"open", "waiting_phone", "assigned"})
PROTECTED_STATUSES = frozenset({"contacted", "resolved", "cancelled", "expired"})


@dataclass(frozen=True)
class ExpireResult:
    scanned: int = 0
    expired_count: int = 0
    skipped_count: int = 0
    expired_ids: tuple[int, ...] = field(default_factory=tuple)
    errors: tuple[str, ...] = field(default_factory=tuple)


def _coerce_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def is_handoff_expirable(
    *,
    status: str,
    created_at: datetime | None,
    expires_at: datetime | None,
    now: datetime,
    expire_hours: int = DEFAULT_EXPIRE_HOURS,
) -> bool:
    """Pure decision: should this handoff row be marked expired?

    Rules:
      - status must be one of {open, waiting_phone, assigned}
      - if expires_at is set and expires_at <= now → expire
      - else fallback: created_at + expire_hours <= now → expire
      - any malformed input → False (skip safely)
    """
    if status not in EXPIRABLE_STATUSES:
        return False
    try:
        now_aware = _coerce_aware(now)
        if now_aware is None:
            return False
        exp_aware = _coerce_aware(expires_at)
        if exp_aware is not None:
            return exp_aware <= now_aware
        created_aware = _coerce_aware(created_at)
        if created_aware is None:
            return False
        if expire_hours is None or expire_hours <= 0:
            return False
        return (now_aware - created_aware) >= timedelta(hours=expire_hours)
    except (TypeError, ValueError, OverflowError):
        return False


class CRMOperatorHandoffService:
    """Service wrapper exposing handoff helpers and DB operations.

    Holds an optional async session for DB-bound methods. All pure helpers
    in this module remain importable without a session.
    """

    EXPIRABLE_STATUSES = EXPIRABLE_STATUSES
    PROTECTED_STATUSES = PROTECTED_STATUSES

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    @staticmethod
    def is_expirable(
        *,
        status: str,
        created_at: datetime | None,
        expires_at: datetime | None,
        now: datetime,
        expire_hours: int = DEFAULT_EXPIRE_HOURS,
    ) -> bool:
        return is_handoff_expirable(
            status=status,
            created_at=created_at,
            expires_at=expires_at,
            now=now,
            expire_hours=expire_hours,
        )

    async def expire_stale_handoffs(
        self,
        now: datetime | None = None,
        expire_hours: int | None = None,
        limit: int = 100,
    ) -> ExpireResult:
        """Mark stale handoff requests as expired.

        Safe: never deletes, only updates status to ``expired``. Sends nothing.

        Args:
            now: reference time (default: utcnow)
            expire_hours: TTL when ``expires_at`` is NULL (default: 24)
            limit: max rows scanned per invocation (default: 100, max: 1000)
        """
        if self._session is None:
            return ExpireResult(errors=("no_session",))

        ref_now = _coerce_aware(now) or datetime.now(UTC)
        hours = expire_hours if expire_hours and expire_hours > 0 else DEFAULT_EXPIRE_HOURS
        batch = max(1, min(int(limit or 100), 1000))

        # Local import — avoid pulling SQLAlchemy at module import time.
        try:
            import sqlalchemy as sa

            from infrastructure.database.models.crm_operator_handoff import (
                CRMOperatorHandoffModel,
            )
        except Exception as exc:  # pragma: no cover - import safety
            return ExpireResult(errors=(f"import_error:{type(exc).__name__}",))

        cutoff_fallback = ref_now - timedelta(hours=hours)
        scanned = 0
        expired_ids: list[int] = []
        skipped = 0
        errors: list[str] = []

        try:
            query = (
                sa.select(CRMOperatorHandoffModel)
                .where(CRMOperatorHandoffModel.status.in_(tuple(EXPIRABLE_STATUSES)))
                .where(
                    sa.or_(
                        sa.and_(
                            CRMOperatorHandoffModel.expires_at.is_not(None),
                            CRMOperatorHandoffModel.expires_at <= ref_now,
                        ),
                        sa.and_(
                            CRMOperatorHandoffModel.expires_at.is_(None),
                            CRMOperatorHandoffModel.created_at <= cutoff_fallback,
                        ),
                    )
                )
                .order_by(CRMOperatorHandoffModel.created_at.asc())
                .limit(batch)
            )
            result = await self._session.execute(query)
            rows = list(result.scalars().all())
        except Exception as exc:
            return ExpireResult(errors=(f"query_error:{type(exc).__name__}",))

        for row in rows:
            scanned += 1
            try:
                if not is_handoff_expirable(
                    status=row.status,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                    now=ref_now,
                    expire_hours=hours,
                ):
                    skipped += 1
                    continue
                row.status = "expired"
                row.updated_at = ref_now
                expired_ids.append(int(row.id))
            except Exception as exc:
                errors.append(f"row_error:{type(exc).__name__}")
                skipped += 1

        if expired_ids:
            try:
                await self._session.commit()
            except Exception as exc:
                try:
                    await self._session.rollback()
                except Exception:
                    pass
                return ExpireResult(
                    scanned=scanned,
                    expired_count=0,
                    skipped_count=scanned,
                    expired_ids=(),
                    errors=tuple(errors + [f"commit_error:{type(exc).__name__}"]),
                )

        return ExpireResult(
            scanned=scanned,
            expired_count=len(expired_ids),
            skipped_count=skipped,
            expired_ids=tuple(expired_ids),
            errors=tuple(errors),
        )
