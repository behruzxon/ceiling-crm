"""
shared.utils.business_hours
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Centralized business-hours logic for the CRM.

All schedulers, follow-up engines, and alert systems rely on these helpers
to avoid sending user-facing messages during off-hours.

Timezone: ``Asia/Tashkent`` (UTC+5) by default, configurable via settings.
Fallback: If timezone resolution fails, uses a fixed UTC+5 offset.

Usage::

    from shared.utils.business_hours import (
        is_business_hours,
        is_off_hours,
        get_local_time,
        get_time_of_day_bucket,
        defer_to_business_hours,
    )

    if is_off_hours():
        next_send = defer_to_business_hours(scheduled_dt)
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

# ── Defaults (used when settings are unavailable) ───────────────────────────

_DEFAULT_TIMEZONE = "Asia/Tashkent"
_DEFAULT_START_HOUR = 9
_DEFAULT_END_HOUR = 20
_FALLBACK_UTC_OFFSET = timezone(timedelta(hours=5))  # UTC+5

# ── Timezone resolution ─────────────────────────────────────────────────────


def _get_tz() -> timezone | ZoneInfo:
    """Return the configured timezone, falling back to UTC+5 on any error."""
    try:
        from shared.config import get_settings

        tz_name = get_settings().business.timezone
    except Exception:
        tz_name = _DEFAULT_TIMEZONE

    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(tz_name)
    except Exception:
        return _FALLBACK_UTC_OFFSET


def _get_hours() -> tuple[int, int]:
    """Return (start_hour, end_hour) from settings or defaults."""
    try:
        from shared.config import get_settings

        s = get_settings().business
        return s.business_hours_start, s.business_hours_end
    except Exception:
        return _DEFAULT_START_HOUR, _DEFAULT_END_HOUR


# ── Public helpers ───────────────────────────────────────────────────────────


def get_local_time() -> datetime:
    """Return the current local time in the configured timezone.

    Falls back to UTC+5 if timezone resolution fails.
    """
    try:
        tz = _get_tz()
        return datetime.now(tz)
    except Exception:
        return datetime.now(_FALLBACK_UTC_OFFSET)


def is_business_hours(dt: datetime | None = None) -> bool:
    """Check whether *dt* (or now) falls within business hours.

    Business hours: ``BUSINESS_HOURS_START`` to ``BUSINESS_HOURS_END``
    (exclusive), any day of the week.

    Falls back to ``True`` (current behaviour) on any error so the system
    never silently stops sending.
    """
    try:
        start, end = _get_hours()
        if dt is None:
            dt = get_local_time()
        else:
            tz = _get_tz()
            dt = dt.astimezone(tz)
        return start <= dt.hour < end
    except Exception:
        return True  # safety: behave like current version


def is_off_hours(dt: datetime | None = None) -> bool:
    """Inverse of :func:`is_business_hours`."""
    return not is_business_hours(dt)


def get_time_of_day_bucket(dt: datetime | None = None) -> str:
    """Classify the current local time into a time-of-day bucket.

    Returns one of: ``"morning"`` | ``"afternoon"`` | ``"evening"`` | ``"night"``.

    Buckets:
      - morning:   06:00–11:59
      - afternoon: 12:00–16:59
      - evening:   17:00–21:59
      - night:     22:00–05:59
    """
    try:
        if dt is None:
            dt = get_local_time()
        else:
            tz = _get_tz()
            dt = dt.astimezone(tz)
        h = dt.hour
    except Exception:
        h = 12  # fallback: afternoon (neutral)

    if 6 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 22:
        return "evening"
    return "night"


def defer_to_business_hours(
    dt: datetime,
    *,
    offset_minutes: int = 5,
) -> datetime:
    """If *dt* is during off-hours, shift it to the next business-hours start.

    The returned datetime is 5 minutes past the start of business hours
    (configurable via *offset_minutes*) to avoid exact-boundary edge cases.

    If *dt* is already within business hours, it is returned unchanged.

    Always returns a timezone-aware datetime.
    """
    try:
        tz = _get_tz()
        start_hour, end_hour = _get_hours()

        local_dt = dt.astimezone(tz)

        if start_hour <= local_dt.hour < end_hour:
            return dt  # already in business hours

        # Compute next business-hours start
        if local_dt.hour >= end_hour:
            # After end → next day at start
            next_day = local_dt.date() + timedelta(days=1)
        else:
            # Before start → same day
            next_day = local_dt.date()

        next_start = datetime.combine(
            next_day,
            time(hour=start_hour, minute=offset_minutes),
            tzinfo=tz,
        )
        return next_start

    except Exception:
        return dt  # safety: return original


def get_off_hours_multiplier(dt: datetime | None = None) -> float:
    """Return a multiplier for time-based thresholds.

    During business hours returns 1.0 (no change).
    During off hours returns 3.0 (triple the threshold).
    """
    try:
        return 1.0 if is_business_hours(dt) else 3.0
    except Exception:
        return 1.0


# ── Constants for downstream consumers ───────────────────────────────────────

TIME_BUCKETS = ("morning", "afternoon", "evening", "night")

# Recommended CTA urgency per bucket
BUCKET_CTA_URGENCY: dict[str, str] = {
    "morning": "action",  # fresh start → action CTA
    "afternoon": "action",  # peak hours → action CTA
    "evening": "soft",  # winding down → softer CTA
    "night": "minimal",  # off hours → minimal CTA
}
