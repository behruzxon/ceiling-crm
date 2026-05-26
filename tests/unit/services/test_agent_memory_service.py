"""Unit tests for AgentMemoryService."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.agent_memory_service import AgentMemoryService
from infrastructure.database.models.agent_memory import AgentMemoryModel
from shared.constants.enums import JourneyEventType


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


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


class TestGetOrCreate:
    @pytest.mark.asyncio
    async def test_returns_existing(self, mock_session: AsyncMock) -> None:
        existing = _make_memory()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        mem = await svc.get_or_create(12345)
        assert mem is existing
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new(self, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        mem = await svc.get_or_create(99999, full_name="Bobur")
        mock_session.add.assert_called_once()
        assert mem.telegram_user_id == 99999
        assert mem.full_name == "Bobur"


class TestUpdateFromEvent:
    @pytest.mark.asyncio
    async def test_opened_catalog(self, mock_session: AsyncMock) -> None:
        mem = _make_memory()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(12345, JourneyEventType.OPENED_CATALOG)
        assert result.last_event_type == "opened_catalog"

    @pytest.mark.asyncio
    async def test_viewed_catalog_item(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(interested_designs=["gulli"])
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(
            12345, JourneyEventType.VIEWED_CATALOG_ITEM, {"design": "mramor"},
        )
        assert "mramor" in result.interested_designs
        assert "gulli" in result.interested_designs

    @pytest.mark.asyncio
    async def test_price_calculated(self, mock_session: AsyncMock) -> None:
        mem = _make_memory()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(
            12345,
            JourneyEventType.PRICE_CALCULATED,
            {"area_m2": 20.0, "design": "gulli", "price": 5_000_000},
        )
        assert result.area_m2 == 20.0
        assert result.ceiling_type == "gulli"
        assert result.estimated_price == 5_000_000
        assert result.lead_temperature == "warm"

    @pytest.mark.asyncio
    async def test_phone_shared_makes_hot(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(lead_temperature="warm")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(
            12345, JourneyEventType.PHONE_SHARED, {"phone": "+998901234567"},
        )
        assert result.lead_temperature == "hot"
        assert result.phone_masked == "+998**…**67"

    @pytest.mark.asyncio
    async def test_operator_requested_disables_followup(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(12345, JourneyEventType.OPERATOR_REQUESTED)
        assert result.followup_enabled is False
        assert result.stop_reason == "operator_requested"

    @pytest.mark.asyncio
    async def test_deal_closed_disables_followup(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(12345, JourneyEventType.DEAL_CLOSED)
        assert result.followup_enabled is False

    @pytest.mark.asyncio
    async def test_clicked_order_warms_cold(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(lead_temperature="cold")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mem
        mock_session.execute.return_value = mock_result

        svc = AgentMemoryService(mock_session)
        result = await svc.update_from_event(12345, JourneyEventType.CLICKED_ORDER)
        assert result.lead_temperature == "warm"


class TestShouldCancelFollowup:
    def test_phone_shared_cancels(self) -> None:
        assert AgentMemoryService.should_cancel_followup_for_event("phone_shared") is True

    def test_operator_requested_cancels(self) -> None:
        assert AgentMemoryService.should_cancel_followup_for_event("operator_requested") is True

    def test_deal_closed_cancels(self) -> None:
        assert AgentMemoryService.should_cancel_followup_for_event("deal_closed") is True

    def test_catalog_does_not_cancel(self) -> None:
        assert AgentMemoryService.should_cancel_followup_for_event("opened_catalog") is False

    def test_price_calculated_does_not_cancel(self) -> None:
        assert AgentMemoryService.should_cancel_followup_for_event("price_calculated") is False
