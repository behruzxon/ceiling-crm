"""Unit tests for JourneyEventService and emit_journey_event helper."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.journey_event_service import (
    JourneyEventService,
    _mask_phone,
    emit_journey_event,
)
from shared.constants.enums import JourneyEventType


class TestJourneyEventType:
    """Verify enum completeness and values."""

    def test_all_event_types_exist(self) -> None:
        expected = {
            "started_bot", "opened_catalog", "viewed_catalog_item",
            "used_price_calculator", "price_calculated", "clicked_order",
            "order_form_started", "order_form_abandoned", "phone_shared",
            "location_shared", "image_sent", "operator_requested",
            "admin_notified", "deal_closed", "lost_lead",
        }
        actual = {e.value for e in JourneyEventType}
        assert expected == actual

    def test_enum_is_string(self) -> None:
        assert isinstance(JourneyEventType.STARTED_BOT, str)
        assert JourneyEventType.STARTED_BOT == "started_bot"


class TestMaskPhone:
    """Verify phone masking for safe storage."""

    def test_mask_normal_phone(self) -> None:
        assert _mask_phone("+998901234567") == "+998**…**67"

    def test_mask_short_phone(self) -> None:
        assert _mask_phone("12345") == "***"

    def test_mask_empty(self) -> None:
        assert _mask_phone("") == "***"

    def test_mask_seven_chars(self) -> None:
        result = _mask_phone("1234567")
        assert result == "1234**…**67"


class TestJourneyEventServiceCreate:
    """Test JourneyEventService.create() method."""

    @pytest.mark.asyncio
    async def test_create_event(self, mock_journey_session: AsyncMock) -> None:
        svc = JourneyEventService(mock_journey_session)
        evt = await svc.create(
            user_id=12345,
            event_type=JourneyEventType.STARTED_BOT,
            event_data={"source": "direct"},
            source_handler="support:cmd_start",
        )
        mock_journey_session.add.assert_called_once()
        mock_journey_session.flush.assert_awaited_once()
        assert evt.user_id == 12345
        assert evt.event_type == "started_bot"
        assert evt.event_data == {"source": "direct"}
        assert evt.source_handler == "support:cmd_start"

    @pytest.mark.asyncio
    async def test_create_with_string_type(self, mock_journey_session: AsyncMock) -> None:
        svc = JourneyEventService(mock_journey_session)
        evt = await svc.create(
            user_id=99,
            event_type="custom_event",
        )
        assert evt.event_type == "custom_event"
        assert evt.event_data == {}

    @pytest.mark.asyncio
    async def test_create_with_none_data(self, mock_journey_session: AsyncMock) -> None:
        svc = JourneyEventService(mock_journey_session)
        evt = await svc.create(
            user_id=1,
            event_type=JourneyEventType.OPENED_CATALOG,
        )
        assert evt.event_data == {}


class TestJourneyEventServiceQueries:
    """Test query methods."""

    @pytest.mark.asyncio
    async def test_get_recent(self, mock_journey_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["evt1", "evt2"]
        mock_journey_session.execute.return_value = mock_result

        svc = JourneyEventService(mock_journey_session)
        events = await svc.get_recent(user_id=123, limit=5)
        assert events == ["evt1", "evt2"]
        mock_journey_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_last(self, mock_journey_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "last_evt"
        mock_journey_session.execute.return_value = mock_result

        svc = JourneyEventService(mock_journey_session)
        result = await svc.get_last(user_id=123, event_type=JourneyEventType.PRICE_CALCULATED)
        assert result == "last_evt"

    @pytest.mark.asyncio
    async def test_get_last_none(self, mock_journey_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_journey_session.execute.return_value = mock_result

        svc = JourneyEventService(mock_journey_session)
        result = await svc.get_last(user_id=123, event_type=JourneyEventType.DEAL_CLOSED)
        assert result is None

    @pytest.mark.asyncio
    async def test_has_recent_true(self, mock_journey_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        mock_journey_session.execute.return_value = mock_result

        svc = JourneyEventService(mock_journey_session)
        assert await svc.has_recent(user_id=1, event_type=JourneyEventType.OPENED_CATALOG) is True

    @pytest.mark.asyncio
    async def test_has_recent_false(self, mock_journey_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_journey_session.execute.return_value = mock_result

        svc = JourneyEventService(mock_journey_session)
        assert await svc.has_recent(user_id=1, event_type=JourneyEventType.DEAL_CLOSED) is False


class TestEmitJourneyEvent:
    """Test the fire-and-forget module-level helper."""

    @pytest.mark.asyncio
    async def test_emit_does_not_raise(self) -> None:
        """Even with broken DB, emit_journey_event must never raise."""
        with patch(
            "infrastructure.database.session.get_session_factory",
            side_effect=RuntimeError("DB down"),
        ):
            await emit_journey_event(
                user_id=1,
                event_type=JourneyEventType.STARTED_BOT,
            )

    @pytest.mark.asyncio
    async def test_emit_masks_phone(self) -> None:
        """Phone in event_data must be masked before DB write."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_ctx

        with patch(
            "infrastructure.database.session.get_session_factory",
            return_value=mock_factory,
        ):
            await emit_journey_event(
                user_id=1,
                event_type=JourneyEventType.PHONE_SHARED,
                event_data={"phone": "+998901234567", "method": "text"},
            )

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.event_data["phone"] == "+998**…**67"
        assert added_obj.event_data["method"] == "text"

    @pytest.mark.asyncio
    async def test_emit_does_not_mutate_original_dict(self) -> None:
        """The caller's dict must not be modified by masking."""
        original = {"phone": "+998901234567"}

        with patch(
            "infrastructure.database.session.get_session_factory",
            side_effect=RuntimeError("DB down"),
        ):
            await emit_journey_event(
                user_id=1,
                event_type=JourneyEventType.PHONE_SHARED,
                event_data=original,
            )

        assert original["phone"] == "+998901234567"
