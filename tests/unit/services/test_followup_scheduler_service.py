"""Unit tests for FollowupSchedulerService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.followup_scheduler_service import (
    _MAX_DAILY_FOLLOWUPS,
    _MAX_TOTAL_FOLLOWUPS,
    FollowupSchedulerService,
)
from infrastructure.database.models.agent_memory import AgentMemoryModel
from infrastructure.database.models.scheduled_followup import ScheduledFollowupModel


def _make_memory(**overrides: object) -> AgentMemoryModel:
    defaults = dict(
        telegram_user_id=12345,
        full_name="Test",
        interested_designs=[],
        lead_temperature="cold",
        followup_enabled=True,
        followup_count=0,
        memory_data={},
    )
    defaults.update(overrides)
    return AgentMemoryModel(**defaults)


def _make_followup(**overrides: object) -> ScheduledFollowupModel:
    defaults = dict(
        telegram_user_id=12345,
        followup_type="catalog",
        trigger_event_type="opened_catalog",
        scheduled_at=datetime.now(UTC),
        status="pending",
        created_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    defaults.update(overrides)
    return ScheduledFollowupModel(**defaults)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestSchedule:
    @pytest.mark.asyncio
    async def test_creates_pending_followup(self, mock_session: AsyncMock) -> None:
        # _has_pending returns 0 (no existing pending)
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        mock_session.execute.return_value = mock_count

        svc = FollowupSchedulerService(mock_session)
        fu = await svc.schedule(12345, "catalog", "opened_catalog", delay_minutes=10)
        assert fu is not None
        assert fu.followup_type == "catalog"
        assert fu.status == "pending"
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_if_pending_exists(self, mock_session: AsyncMock) -> None:
        mock_count = MagicMock()
        mock_count.scalar.return_value = 1
        mock_session.execute.return_value = mock_count

        svc = FollowupSchedulerService(mock_session)
        fu = await svc.schedule(12345, "catalog", "opened_catalog")
        assert fu is None
        mock_session.add.assert_not_called()


class TestShouldSend:
    @staticmethod
    def _mock_scalar(value: int) -> MagicMock:
        r = MagicMock()
        r.scalar.return_value = value
        return r

    @pytest.mark.asyncio
    async def test_ok_when_all_conditions_pass(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True, followup_count=0, last_followup_at=None)
        fu = _make_followup()

        # Two execute calls: _count_sent_today(0) + _is_stale(0)
        mock_session.execute.side_effect = [self._mock_scalar(0), self._mock_scalar(0)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is True
        assert reason == "ok"

    @pytest.mark.asyncio
    async def test_disabled_followup(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=False, stop_reason="operator_requested")
        fu = _make_followup()

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is False
        assert "disabled" in reason

    @pytest.mark.asyncio
    async def test_lifetime_cap(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_count=_MAX_TOTAL_FOLLOWUPS)
        fu = _make_followup()

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is False
        assert reason == "lifetime_cap"

    @pytest.mark.asyncio
    async def test_daily_cap(self, mock_session: AsyncMock) -> None:
        mem = _make_memory()
        fu = _make_followup()

        mock_session.execute.side_effect = [self._mock_scalar(_MAX_DAILY_FOLLOWUPS)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is False
        assert reason == "daily_cap"

    @pytest.mark.asyncio
    async def test_min_gap(self, mock_session: AsyncMock) -> None:
        recent = datetime.now(UTC) - timedelta(seconds=30)
        mem = _make_memory(last_followup_at=recent)
        fu = _make_followup()

        # daily count = 0, but gap check fails before stale
        mock_session.execute.side_effect = [self._mock_scalar(0)]

        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is False
        assert reason == "min_gap"

    @pytest.mark.asyncio
    async def test_no_memory(self, mock_session: AsyncMock) -> None:
        fu = _make_followup()
        svc = FollowupSchedulerService(mock_session)
        ok, reason = await svc.should_send(fu, None)
        assert ok is False
        assert reason == "no_memory"


class TestStaleCheck:
    @pytest.mark.asyncio
    async def test_catalog_stale_after_price(self, mock_session: AsyncMock) -> None:
        """Catalog follow-up should be stale if user calculated price after scheduling."""
        fu = _make_followup(followup_type="catalog")

        mock_result = MagicMock()
        mock_result.scalar.return_value = 1  # superseding event exists
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_price_stale_after_order(self, mock_session: AsyncMock) -> None:
        """Price follow-up should be stale if user started order after scheduling."""
        fu = _make_followup(followup_type="price")

        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_abandoned_order_stale_after_phone(self, mock_session: AsyncMock) -> None:
        """Abandoned order follow-up should be stale if user shared phone."""
        fu = _make_followup(followup_type="abandoned_order")

        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is True

    @pytest.mark.asyncio
    async def test_not_stale_when_no_superseding(self, mock_session: AsyncMock) -> None:
        fu = _make_followup(followup_type="catalog")

        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        is_stale = await svc._is_stale(fu)
        assert is_stale is False


class TestStopSignal:
    def test_kerak_emas(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("kerak emas") is True

    def test_stop(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("Stop") is True

    def test_bekor(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("BEKOR") is True

    def test_russian_stop(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("стоп") is True

    def test_russian_ne_nado(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("не надо") is True

    def test_yozmang(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("yozmang") is True

    def test_normal_message_not_stop(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("Salom") is False

    def test_price_question_not_stop(self) -> None:
        assert FollowupSchedulerService.is_stop_signal("Narxi qancha?") is False


class TestBuildMessage:
    def test_catalog_message(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("catalog")
        assert "Katalog" in text
        assert len(buttons) == 3

    def test_price_message_has_buttons(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("price")
        assert "Hisob" in text
        assert len(buttons) == 3

    def test_abandoned_order_message_has_buttons(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("abandoned_order")
        assert "Buyurtma" in text or "davom" in text
        assert len(buttons) == 3

    def test_unknown_type_empty(self) -> None:
        text, buttons = FollowupSchedulerService.build_message("unknown")
        assert text == ""
        assert buttons == []


class TestCancelAllPending:
    @pytest.mark.asyncio
    async def test_cancels_and_returns_count(self, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        svc = FollowupSchedulerService(mock_session)
        count = await svc.cancel_all_pending(12345, "operator_requested")
        assert count == 3
