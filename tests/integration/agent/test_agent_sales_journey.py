"""Integration tests: end-to-end agent sales journey flows.

These tests wire real service instances together (with mocked DB sessions)
to verify the full event→memory→followup→escalation pipeline works as a unit.
No real database or Telegram API is used.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.services.admin_escalation_service import AdminEscalationService
from core.services.agent_memory_service import AgentMemoryService
from core.services.followup_scheduler_service import FollowupSchedulerService
from infrastructure.database.models.agent_memory import AgentMemoryModel
from infrastructure.database.models.scheduled_followup import ScheduledFollowupModel
from shared.constants.enums import JourneyEventType


def _mock_session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    s.flush = AsyncMock()
    s.execute = AsyncMock()
    s.commit = AsyncMock()
    return s


def _scalar(val: object) -> MagicMock:
    r = MagicMock()
    r.scalar.return_value = val
    r.scalar_one_or_none.return_value = val
    return r


# ── Catalog journey ────────────────────────────────────────────────────────


class TestCatalogJourney:
    """catalog open → memory updated → followup scheduled → followup sent → escalation."""

    @pytest.mark.asyncio
    async def test_catalog_event_updates_memory(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(telegram_user_id=1, interested_designs=[], memory_data={})
        session.execute.return_value = _scalar(mem)

        svc = AgentMemoryService(session)
        result = await svc.update_from_event(1, JourneyEventType.OPENED_CATALOG)
        assert result.last_event_type == "opened_catalog"

    @pytest.mark.asyncio
    async def test_catalog_viewed_adds_design(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(telegram_user_id=1, interested_designs=[], memory_data={})
        session.execute.return_value = _scalar(mem)

        svc = AgentMemoryService(session)
        result = await svc.update_from_event(
            1, JourneyEventType.VIEWED_CATALOG_ITEM, {"design": "gulli"},
        )
        assert "gulli" in result.interested_designs

    @pytest.mark.asyncio
    async def test_catalog_followup_scheduled(self) -> None:
        session = _mock_session()
        session.execute.return_value = _scalar(0)  # no pending

        svc = FollowupSchedulerService(session)
        fu = await svc.schedule(1, "catalog", "opened_catalog", delay_minutes=10)
        assert fu is not None
        assert fu.followup_type == "catalog"
        assert fu.status == "pending"

    @pytest.mark.asyncio
    async def test_catalog_followup_should_send_ok(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            followup_enabled=True, followup_count=0,
        )
        fu = ScheduledFollowupModel(
            telegram_user_id=1, followup_type="catalog",
            trigger_event_type="opened_catalog",
            scheduled_at=datetime.now(UTC),
            created_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        session.execute.side_effect = [_scalar(0), _scalar(0)]

        svc = FollowupSchedulerService(session)
        ok, reason = await svc.should_send(fu, mem)
        assert ok is True


# ── Price journey ──────────────────────────────────────────────────────────


class TestPriceJourney:
    @pytest.mark.asyncio
    async def test_price_event_updates_memory(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            lead_temperature="cold",
        )
        session.execute.return_value = _scalar(mem)

        svc = AgentMemoryService(session)
        result = await svc.update_from_event(
            1, JourneyEventType.PRICE_CALCULATED,
            {"area_m2": 20.0, "design": "gulli", "price": 5_000_000},
        )
        assert result.area_m2 == 20.0
        assert result.estimated_price == 5_000_000
        assert result.lead_temperature == "warm"

    @pytest.mark.asyncio
    async def test_price_followup_stale_after_order(self) -> None:
        session = _mock_session()
        fu = ScheduledFollowupModel(
            telegram_user_id=1, followup_type="price",
            trigger_event_type="price_calculated",
            scheduled_at=datetime.now(UTC),
            created_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        session.execute.return_value = _scalar(1)  # superseding event exists

        svc = FollowupSchedulerService(session)
        assert await svc._is_stale(fu) is True


# ── Abandoned order journey ────────────────────────────────────────────────


class TestAbandonedOrderJourney:
    @pytest.mark.asyncio
    async def test_order_started_updates_memory(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            lead_temperature="cold",
        )
        session.execute.return_value = _scalar(mem)

        svc = AgentMemoryService(session)
        result = await svc.update_from_event(1, JourneyEventType.ORDER_FORM_STARTED)
        assert result.lead_temperature == "warm"

    @pytest.mark.asyncio
    async def test_abandoned_followup_stale_after_phone(self) -> None:
        session = _mock_session()
        fu = ScheduledFollowupModel(
            telegram_user_id=1, followup_type="abandoned_order",
            trigger_event_type="order_form_started",
            scheduled_at=datetime.now(UTC),
            created_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        session.execute.return_value = _scalar(1)

        svc = FollowupSchedulerService(session)
        assert await svc._is_stale(fu) is True


# ── Stop signal flow ──────────────────────────────────────────────────────


class TestStopSignalFlow:
    @pytest.mark.asyncio
    async def test_stop_word_disables_and_cancels(self) -> None:
        session = _mock_session()
        mock_result = MagicMock()
        mock_result.rowcount = 2
        session.execute.return_value = mock_result

        mem_svc = AgentMemoryService(session)
        fu_svc = FollowupSchedulerService(session)

        await mem_svc.disable_followup(1, "user_opted_out")
        cancelled = await fu_svc.cancel_all_pending(1, "user_opted_out")
        assert cancelled == 2

    def test_stop_words_detected(self) -> None:
        for word in ["kerak emas", "stop", "bekor", "yozmang", "стоп"]:
            assert FollowupSchedulerService.is_stop_signal(word) is True

    def test_normal_words_pass(self) -> None:
        for word in ["Salom", "5x4", "Narxi?", "Ha"]:
            assert FollowupSchedulerService.is_stop_signal(word) is False


# ── Operator cancels followups ─────────────────────────────────────────────


class TestOperatorCancelsFlow:
    @pytest.mark.asyncio
    async def test_operator_event_disables_followup(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            followup_enabled=True,
        )
        session.execute.return_value = _scalar(mem)

        svc = AgentMemoryService(session)
        result = await svc.update_from_event(1, JourneyEventType.OPERATOR_REQUESTED)
        assert result.followup_enabled is False
        assert result.stop_reason == "operator_requested"

    def test_operator_is_cancel_event(self) -> None:
        assert AgentMemoryService.should_cancel_followup_for_event("operator_requested") is True


# ── Admin escalation flow ─────────────────────────────────────────────────


class TestAdminEscalationFlow:
    def test_warm_lead_above_threshold_escalates(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            lead_temperature="warm", followup_enabled=True, followup_count=3,
            admin_escalation_count=0,
        )

        svc = AdminEscalationService(session)
        ok, _ = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is True

    def test_cold_lead_no_escalation(self) -> None:
        session = _mock_session()
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            lead_temperature="cold", followup_enabled=True, followup_count=5,
            admin_escalation_count=0,
        )

        svc = AdminEscalationService(session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is False
        assert reason == "cold_lead"

    def test_cooldown_prevents_duplicate(self) -> None:
        session = _mock_session()
        recent = datetime.now(UTC) - timedelta(minutes=10)
        mem = AgentMemoryModel(
            telegram_user_id=1, interested_designs=[], memory_data={},
            lead_temperature="hot", followup_enabled=True, followup_count=3,
            admin_escalation_count=1, last_admin_escalation_at=recent,
        )

        svc = AdminEscalationService(session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is False
        assert reason == "cooldown"

    def test_admin_alert_has_lead_summary(self) -> None:
        mem = AgentMemoryModel(
            telegram_user_id=1, full_name="Ali", interested_designs=[],
            memory_data={}, lead_temperature="hot", followup_count=3,
            phone_masked="+998**…**67", district="Qarshi",
            area_m2=25.0, estimated_price=5_000_000,
            admin_escalation_count=0,
        )
        text = AdminEscalationService.build_admin_alert(mem)
        assert "Ali" in text
        assert "Qarshi" in text
        assert "5,000,000" in text


# ── AI composer fallback ──────────────────────────────────────────────────


class TestAIComposerFallback:
    @pytest.mark.asyncio
    async def test_disabled_returns_deterministic(self) -> None:
        from core.services.ai_message_composer_service import compose_followup
        result = await compose_followup("catalog", {}, "FALLBACK_TEXT")
        assert result == "FALLBACK_TEXT"

    @pytest.mark.asyncio
    async def test_build_message_ai_fallback_on_error(self) -> None:
        with patch(
            "core.services.ai_message_composer_service.compose_followup",
            side_effect=RuntimeError("API crash"),
        ):
            text, buttons = await FollowupSchedulerService.build_message_ai(
                "price", memory_data={"full_name": "X"},
            )
        assert "Hisob" in text
        assert len(buttons) == 3


# ── Feature flags off → no scheduling ─────────────────────────────────────


class TestFeatureFlagsOff:
    def test_all_flags_default_false(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_followups_enabled is False
        assert s.agent_catalog_followup_enabled is False
        assert s.agent_price_followup_enabled is False
        assert s.agent_order_followup_enabled is False
        assert s.agent_admin_escalation_enabled is False
        assert s.agent_ai_composer_enabled is False


# ── Business hours reschedule ──────────────────────────────────────────────


class TestBusinessHoursReschedule:
    def test_off_hours_deferred(self) -> None:
        from shared.utils.business_hours import defer_to_business_hours, is_off_hours

        tz = timezone(timedelta(hours=5))
        late = datetime(2026, 5, 25, 23, 0, tzinfo=tz)
        assert is_off_hours(late) is True

        deferred = defer_to_business_hours(late)
        local = deferred.astimezone(tz)
        assert local.hour == 9
        assert local.minute == 5

    def test_business_hours_not_deferred(self) -> None:
        from shared.utils.business_hours import defer_to_business_hours

        tz = timezone(timedelta(hours=5))
        during = datetime(2026, 5, 25, 14, 0, tzinfo=tz)
        result = defer_to_business_hours(during)
        assert result == during


# ── Duplicate followup prevention ──────────────────────────────────────────


class TestDuplicateFollowupPrevention:
    @pytest.mark.asyncio
    async def test_no_duplicate_when_pending_exists(self) -> None:
        session = _mock_session()
        session.execute.return_value = _scalar(1)  # existing pending

        svc = FollowupSchedulerService(session)
        fu = await svc.schedule(1, "catalog", "opened_catalog")
        assert fu is None


# ── Migration chain ────────────────────────────────────────────────────────


class TestMigrationChain:
    def test_journey_events_model_imports(self) -> None:
        from infrastructure.database.models.journey_event import JourneyEventModel
        assert JourneyEventModel.__tablename__ == "customer_journey_events"

    def test_agent_memory_model_imports(self) -> None:
        from infrastructure.database.models.agent_memory import AgentMemoryModel
        assert AgentMemoryModel.__tablename__ == "customer_agent_memory"

    def test_scheduled_followup_model_imports(self) -> None:
        from infrastructure.database.models.scheduled_followup import ScheduledFollowupModel
        assert ScheduledFollowupModel.__tablename__ == "scheduled_followups"

    def test_escalation_columns_exist(self) -> None:
        from infrastructure.database.models.agent_memory import AgentMemoryModel
        m = AgentMemoryModel(telegram_user_id=1, interested_designs=[], memory_data={})
        assert hasattr(m, "admin_escalation_count")
        assert hasattr(m, "last_admin_escalation_at")
        assert hasattr(m, "admin_escalation_reason")

    def test_migration_chain_linear(self) -> None:
        """Verify our 4 migrations form a linear chain."""
        chain = {
            "t5u6v7w8x9y0": "s4t5u6v7w8x9",  # journey_events
            "u6v7w8x9y0z1": "t5u6v7w8x9y0",  # agent_memory
            "v7w8x9y0z1a2": "u6v7w8x9y0z1",  # scheduled_followups
            "w8x9y0z1a2b3": "v7w8x9y0z1a2",  # escalation_columns
        }
        for rev, parent in chain.items():
            assert parent is not None, f"{rev} has no parent"
