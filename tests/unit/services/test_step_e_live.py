"""Step E tests: business hours, feature flags, Redis fallback, stop words, buttons."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.followup_scheduler_service import FollowupSchedulerService
from infrastructure.database.models.agent_memory import AgentMemoryModel
from infrastructure.database.models.scheduled_followup import ScheduledFollowupModel


def _make_memory(**kw: object) -> AgentMemoryModel:
    defaults = {
        "telegram_user_id": 12345,
        "full_name": "Test",
        "interested_designs": [],
        "lead_temperature": "cold",
        "followup_enabled": True,
        "followup_count": 0,
        "memory_data": {},
    }
    defaults.update(kw)
    return AgentMemoryModel(**defaults)


def _make_followup(**kw: object) -> ScheduledFollowupModel:
    defaults = {
        "telegram_user_id": 12345,
        "followup_type": "catalog",
        "trigger_event_type": "opened_catalog",
        "scheduled_at": datetime.now(UTC),
        "status": "pending",
        "created_at": datetime.now(UTC) - timedelta(minutes=10),
    }
    defaults.update(kw)
    return ScheduledFollowupModel(**defaults)


# ── Business hours ──────────────────────────────────────────────────────────


class TestBusinessHours:
    def test_is_business_hours_inside(self) -> None:
        from shared.utils.business_hours import is_business_hours

        tz = timezone(timedelta(hours=5))
        dt = datetime(2026, 5, 25, 14, 0, tzinfo=tz)
        assert is_business_hours(dt) is True

    def test_is_off_hours_after_close(self) -> None:
        from shared.utils.business_hours import is_off_hours

        tz = timezone(timedelta(hours=5))
        dt = datetime(2026, 5, 25, 22, 0, tzinfo=tz)
        assert is_off_hours(dt) is True

    def test_is_off_hours_before_open(self) -> None:
        from shared.utils.business_hours import is_off_hours

        tz = timezone(timedelta(hours=5))
        dt = datetime(2026, 5, 25, 7, 0, tzinfo=tz)
        assert is_off_hours(dt) is True

    def test_defer_to_next_morning(self) -> None:
        from shared.utils.business_hours import defer_to_business_hours

        tz = timezone(timedelta(hours=5))
        late_night = datetime(2026, 5, 25, 23, 30, tzinfo=tz)
        deferred = defer_to_business_hours(late_night)
        deferred_local = deferred.astimezone(tz)
        assert deferred_local.hour == 9
        assert deferred_local.minute == 5
        assert deferred_local.day == 26

    def test_defer_before_open_same_day(self) -> None:
        from shared.utils.business_hours import defer_to_business_hours

        tz = timezone(timedelta(hours=5))
        early = datetime(2026, 5, 25, 6, 0, tzinfo=tz)
        deferred = defer_to_business_hours(early)
        deferred_local = deferred.astimezone(tz)
        assert deferred_local.hour == 9
        assert deferred_local.minute == 5
        assert deferred_local.day == 25


# ── Feature flags ──────────────────────────────────────────────────────────


class TestFeatureFlags:
    def test_flags_default_false(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_followups_enabled is False
        assert s.agent_catalog_followup_enabled is False
        assert s.agent_price_followup_enabled is False
        assert s.agent_order_followup_enabled is False

    def test_delay_default_10(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_catalog_followup_delay_minutes == 10


# ── Stop words ──────────────────────────────────────────────────────────────


class TestStopWords:
    @pytest.mark.parametrize(
        "word",
        [
            "kerak emas",
            "kerakmas",
            "stop",
            "bekor",
            "yozmang",
            "qiziqmayman",
            "hozir emas",
            "не надо",
            "стоп",
            "отмена",
        ],
    )
    def test_stop_words_detected(self, word: str) -> None:
        assert FollowupSchedulerService.is_stop_signal(word) is True

    @pytest.mark.parametrize(
        "word",
        [
            "Salom",
            "Narxi qancha?",
            "Ha",
            "Yo'q",
            "5x4",
            "Gulli",
            "rahmat",
            "ok",
        ],
    )
    def test_normal_words_not_stop(self, word: str) -> None:
        assert FollowupSchedulerService.is_stop_signal(word) is False


# ── Catalog buttons ─────────────────────────────────────────────────────────


class TestCatalogButtons:
    def test_catalog_message_has_three_buttons(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("catalog")
        assert len(buttons) == 3
        labels = [b[0] for b in buttons]
        assert "💰 Narx hisoblash" in labels
        assert "🛒 Zakaz berish" in labels
        assert "👨‍💼 Operator" in labels

    def test_catalog_message_text(self) -> None:
        text, _ = FollowupSchedulerService.build_message("catalog")
        assert "Katalog" in text
        assert "kvadrat" in text.lower()


# ── Reschedule method ──────────────────────────────────────────────────────


class TestReschedule:
    @pytest.mark.asyncio
    async def test_reschedule_updates_time(self) -> None:
        session = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()

        svc = FollowupSchedulerService(session)
        new_time = datetime(2026, 5, 26, 9, 5, tzinfo=UTC)
        await svc.reschedule(42, new_time)
        session.execute.assert_awaited_once()
        session.flush.assert_awaited_once()


# ── Redis fallback ──────────────────────────────────────────────────────────


class TestRedisFallback:
    @pytest.mark.asyncio
    async def test_redis_unavailable_db_fallback_works(self) -> None:
        """When Redis is down, should_send still works via DB checks."""
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        session.execute.side_effect = [mock_result, mock_result]

        mem = _make_memory(followup_enabled=True, followup_count=0)
        fu = _make_followup()

        svc = FollowupSchedulerService(session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is True
        assert reason == "ok"

    @pytest.mark.asyncio
    async def test_redis_pre_check_passes_when_redis_down(self) -> None:
        """_redis_pre_check returns (True, 'redis_unavailable') when Redis fails."""
        from apps.scheduler.jobs.agent_followup_jobs import _redis_pre_check

        with patch(
            "infrastructure.cache.client.get_redis",
            side_effect=RuntimeError("Redis down"),
        ):
            ok, reason = await _redis_pre_check(12345, "catalog")
        assert ok is True
        assert reason == "redis_unavailable"


# ── Configurable delay ─────────────────────────────────────────────────────


class TestConfigurableDelay:
    def test_delay_field_accepts_1_minute(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings(AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=1)
        assert s.agent_catalog_followup_delay_minutes == 1

    def test_delay_field_rejects_zero(self) -> None:
        from shared.config.settings import BusinessSettings

        with pytest.raises(Exception):
            BusinessSettings(AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=0)
