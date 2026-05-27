"""Step F tests: price follow-up feature flag, delay, buttons, stale checks."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

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
        "followup_type": "price",
        "trigger_event_type": "price_calculated",
        "scheduled_at": datetime.now(UTC),
        "status": "pending",
        "created_at": datetime.now(UTC) - timedelta(minutes=10),
    }
    defaults.update(kw)
    return ScheduledFollowupModel(**defaults)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


# ── Feature flags ──────────────────────────────────────────────────────────


class TestPriceFeatureFlag:
    def test_price_flag_default_false(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_price_followup_enabled is False

    def test_price_delay_default_10(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_price_followup_delay_minutes == 10

    def test_price_delay_accepts_1(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings(AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=1)
        assert s.agent_price_followup_delay_minutes == 1

    def test_price_delay_rejects_zero(self) -> None:
        from shared.config.settings import BusinessSettings
        with pytest.raises(Exception):
            BusinessSettings(AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=0)


# ── Price message & buttons ────────────────────────────────────────────────


class TestPriceMessage:
    def test_price_message_text(self) -> None:
        text, _ = FollowupSchedulerService.build_message("price")
        assert "Hisob-kitob" in text
        assert "😊" in text

    def test_price_buttons_count(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("price")
        assert len(buttons) == 3

    def test_price_buttons_labels(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("price")
        labels = [b[0] for b in buttons]
        assert "🛒 Zakaz berish" in labels
        assert "👨‍💼 Operator" in labels
        assert "❌ Kerak emas" in labels

    def test_price_buttons_callbacks(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("price")
        callbacks = [b[1] for b in buttons]
        assert "agentfu:order" in callbacks
        assert "agentfu:operator" in callbacks
        assert "agentfu:stop" in callbacks


# ── Stale checks for price ─────────────────────────────────────────────────


class TestPriceStale:
    @staticmethod
    def _mock_scalar(value: int) -> MagicMock:
        r = MagicMock()
        r.scalar.return_value = value
        return r

    @pytest.mark.asyncio
    async def test_price_stale_after_order_started(self, mock_session: AsyncMock) -> None:
        fu = _make_followup(followup_type="price")
        mock_session.execute.return_value = self._mock_scalar(1)

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_price_stale_after_phone_shared(self, mock_session: AsyncMock) -> None:
        fu = _make_followup(followup_type="price")
        mock_session.execute.return_value = self._mock_scalar(1)

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_price_not_stale_when_no_superseding(self, mock_session: AsyncMock) -> None:
        fu = _make_followup(followup_type="price")
        mock_session.execute.return_value = self._mock_scalar(0)

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is False

    @pytest.mark.asyncio
    async def test_price_should_send_ok(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True, followup_count=0)
        fu = _make_followup()

        mock_session.execute.side_effect = [self._mock_scalar(0), self._mock_scalar(0)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is True

    @pytest.mark.asyncio
    async def test_price_should_send_stale(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True, followup_count=0)
        fu = _make_followup()

        # daily_count=0, stale=1
        mock_session.execute.side_effect = [self._mock_scalar(0), self._mock_scalar(1)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is False
        assert reason == "stale"

    @pytest.mark.asyncio
    async def test_price_operator_cancels_pending(self, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.rowcount = 2
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        count = await svc.cancel_all_pending(12345, "operator_requested")
        assert count == 2


# ── Business hours apply to price ──────────────────────────────────────────


class TestPriceBusinessHours:
    def test_business_hours_check_works(self) -> None:
        from shared.utils.business_hours import is_business_hours

        tz = timezone(timedelta(hours=5))
        during = datetime(2026, 5, 25, 14, 0, tzinfo=tz)
        assert is_business_hours(during) is True

        after = datetime(2026, 5, 25, 22, 0, tzinfo=tz)
        assert is_business_hours(after) is False
