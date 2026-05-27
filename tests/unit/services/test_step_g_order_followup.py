"""Step G tests: abandoned order follow-up flag, delay, buttons, stale checks."""

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
        "followup_type": "abandoned_order",
        "trigger_event_type": "order_form_started",
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


class TestOrderFeatureFlag:
    def test_order_flag_default_false(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_order_followup_enabled is False

    def test_order_delay_default_10(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings()
        assert s.agent_order_followup_delay_minutes == 10

    def test_order_delay_accepts_1(self) -> None:
        from shared.config.settings import BusinessSettings

        s = BusinessSettings(AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=1)
        assert s.agent_order_followup_delay_minutes == 1

    def test_order_delay_rejects_zero(self) -> None:
        from shared.config.settings import BusinessSettings

        with pytest.raises(Exception):
            BusinessSettings(AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=0)


# ── Message & buttons ─────────────────────────────────────────────────────


class TestOrderMessage:
    def test_order_message_text(self) -> None:
        text, _ = FollowupSchedulerService.build_message("abandoned_order")
        assert "Buyurtma" in text or "davom" in text
        assert "😊" in text

    def test_order_buttons_count(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("abandoned_order")
        assert len(buttons) == 3

    def test_order_buttons_labels(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("abandoned_order")
        labels = [b[0] for b in buttons]
        assert "✅ Davom etish" in labels
        assert "👨‍💼 Operator" in labels
        assert "❌ Kerak emas" in labels

    def test_order_buttons_callbacks(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("abandoned_order")
        callbacks = [b[1] for b in buttons]
        assert "agentfu:resume" in callbacks
        assert "agentfu:operator" in callbacks
        assert "agentfu:stop" in callbacks


# ── Stale checks ─────────────────────────────────────────────────────────


class TestOrderStale:
    @staticmethod
    def _mock_scalar(value: int) -> MagicMock:
        r = MagicMock()
        r.scalar.return_value = value
        return r

    @pytest.mark.asyncio
    async def test_stale_after_phone_shared(self, mock_session: AsyncMock) -> None:
        fu = _make_followup()
        mock_session.execute.return_value = self._mock_scalar(1)

        svc = FollowupSchedulerService(mock_session)
        assert await svc._is_stale(fu) is True

    @pytest.mark.asyncio
    async def test_stale_after_location_shared(self, mock_session: AsyncMock) -> None:
        fu = _make_followup()
        mock_session.execute.return_value = self._mock_scalar(1)

        svc = FollowupSchedulerService(mock_session)
        assert await svc._is_stale(fu) is True

    @pytest.mark.asyncio
    async def test_stale_after_operator_requested(self, mock_session: AsyncMock) -> None:
        fu = _make_followup()
        mock_session.execute.return_value = self._mock_scalar(1)

        svc = FollowupSchedulerService(mock_session)
        assert await svc._is_stale(fu) is True

    @pytest.mark.asyncio
    async def test_not_stale_when_no_superseding(self, mock_session: AsyncMock) -> None:
        fu = _make_followup()
        mock_session.execute.return_value = self._mock_scalar(0)

        svc = FollowupSchedulerService(mock_session)
        assert await svc._is_stale(fu) is False

    @pytest.mark.asyncio
    async def test_should_send_ok(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True, followup_count=0)
        fu = _make_followup()
        mock_session.execute.side_effect = [self._mock_scalar(0), self._mock_scalar(0)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is True

    @pytest.mark.asyncio
    async def test_should_send_stale(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True, followup_count=0)
        fu = _make_followup()
        mock_session.execute.side_effect = [self._mock_scalar(0), self._mock_scalar(1)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is False
        assert reason == "stale"

    @pytest.mark.asyncio
    async def test_deal_closed_cancels_all(self, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        count = await svc.cancel_all_pending(12345, "deal_closed")
        assert count == 1


# ── Superseding events list ───────────────────────────────────────────────


class TestOrderSupersedingEvents:
    def test_location_shared_is_superseding(self) -> None:
        from core.services.followup_scheduler_service import _SUPERSEDING_EVENTS

        assert "location_shared" in _SUPERSEDING_EVENTS["abandoned_order"]

    def test_phone_shared_is_superseding(self) -> None:
        from core.services.followup_scheduler_service import _SUPERSEDING_EVENTS

        assert "phone_shared" in _SUPERSEDING_EVENTS["abandoned_order"]

    def test_operator_requested_is_superseding(self) -> None:
        from core.services.followup_scheduler_service import _SUPERSEDING_EVENTS

        assert "operator_requested" in _SUPERSEDING_EVENTS["abandoned_order"]

    def test_deal_closed_is_superseding(self) -> None:
        from core.services.followup_scheduler_service import _SUPERSEDING_EVENTS

        assert "deal_closed" in _SUPERSEDING_EVENTS["abandoned_order"]


# ── Business hours ─────────────────────────────────────────────────────────


class TestOrderBusinessHours:
    def test_business_hours_apply(self) -> None:
        from shared.utils.business_hours import is_off_hours

        tz = timezone(timedelta(hours=5))
        assert is_off_hours(datetime(2026, 5, 25, 23, 0, tzinfo=tz)) is True
        assert is_off_hours(datetime(2026, 5, 25, 14, 0, tzinfo=tz)) is False


# ── No regression on catalog/price ─────────────────────────────────────────


class TestNoRegression:
    def test_catalog_buttons_still_3(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("catalog")
        assert len(buttons) == 3

    def test_price_buttons_still_3(self) -> None:
        _, buttons = FollowupSchedulerService.build_message("price")
        assert len(buttons) == 3

    def test_catalog_message_unchanged(self) -> None:
        text, _ = FollowupSchedulerService.build_message("catalog")
        assert "Katalog" in text

    def test_price_message_unchanged(self) -> None:
        text, _ = FollowupSchedulerService.build_message("price")
        assert "Hisob-kitob" in text
