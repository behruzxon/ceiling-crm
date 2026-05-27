"""Step H tests: admin escalation service, flags, cooldown, message format."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.admin_escalation_service import AdminEscalationService
from infrastructure.database.models.agent_memory import AgentMemoryModel


def _make_memory(**kw: object) -> AgentMemoryModel:
    defaults = {
        "telegram_user_id": 12345,
        "full_name": "Bobur",
        "interested_designs": [],
        "lead_temperature": "warm",
        "followup_enabled": True,
        "followup_count": 3,
        "memory_data": {},
        "admin_escalation_count": 0,
    }
    defaults.update(kw)
    return AgentMemoryModel(**defaults)


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    return session


# ── Feature flags ──────────────────────────────────────────────────────────


class TestEscalationFlags:
    def test_flag_default_false(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_admin_escalation_enabled is False

    def test_threshold_default_2(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_admin_escalation_after_followups == 2

    def test_cooldown_default_60(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_admin_escalation_cooldown_minutes == 60


# ── should_escalate ──────────────────────────────────────────────────────


class TestShouldEscalate:
    def test_warm_lead_above_threshold(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(lead_temperature="warm", followup_count=3)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is True

    def test_hot_lead_above_threshold(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(lead_temperature="hot", followup_count=2)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is True

    def test_cold_lead_no_escalation(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(lead_temperature="cold", followup_count=5)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is False
        assert reason == "cold_lead"

    def test_below_threshold(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_count=1)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is False
        assert reason == "below_threshold"

    def test_followup_disabled(self, mock_session: AsyncMock) -> None:
        mem = _make_memory(followup_enabled=False, followup_count=5)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is False
        assert reason == "followup_disabled"

    def test_cooldown_active(self, mock_session: AsyncMock) -> None:
        recent = datetime.now(UTC) - timedelta(minutes=10)
        mem = _make_memory(last_admin_escalation_at=recent, followup_count=3)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is False
        assert reason == "cooldown"

    def test_cooldown_expired(self, mock_session: AsyncMock) -> None:
        old = datetime.now(UTC) - timedelta(minutes=120)
        mem = _make_memory(last_admin_escalation_at=old, followup_count=3)
        svc = AdminEscalationService(mock_session)
        ok, reason = svc.should_escalate(mem, threshold=2, cooldown_minutes=60)
        assert ok is True


# ── Admin alert message ──────────────────────────────────────────────────


class TestAdminAlert:
    def test_alert_contains_lead_info(self) -> None:
        mem = _make_memory(
            full_name="Bobur",
            phone_masked="+998**…**67",
            district="Qarshi",
            area_m2=25.0,
            ceiling_type="gulli",
            estimated_price=5_000_000,
            lead_temperature="hot",
            last_event_type="price_calculated",
            followup_count=3,
        )
        text = AdminEscalationService.build_admin_alert(mem)
        assert "Bobur" in text
        assert "+998**…**67" in text
        assert "Qarshi" in text
        assert "25.0 m²" in text
        assert "gulli" in text
        assert "5,000,000 UZS" in text
        assert "hot" in text
        assert "price_calculated" in text
        assert "JIM QOLDI" in text
        assert "Tavsiya" in text

    def test_alert_handles_missing_data(self) -> None:
        mem = _make_memory(
            full_name=None,
            phone_masked=None,
            district=None,
            area_m2=None,
            ceiling_type=None,
            estimated_price=None,
        )
        text = AdminEscalationService.build_admin_alert(mem)
        assert "Noma'lum" in text or "noma'lum" in text
        assert "—" in text

    def test_hot_lead_has_fire_emoji(self) -> None:
        mem = _make_memory(lead_temperature="hot")
        text = AdminEscalationService.build_admin_alert(mem)
        assert "🔥" in text

    def test_warm_lead_has_yellow_emoji(self) -> None:
        mem = _make_memory(lead_temperature="warm")
        text = AdminEscalationService.build_admin_alert(mem)
        assert "🟡" in text


# ── Admin keyboard ────────────────────────────────────────────────────────


class TestAdminKeyboard:
    def test_keyboard_has_3_buttons(self) -> None:
        rows = AdminEscalationService.build_admin_keyboard(12345)
        all_buttons = [btn for row in rows for btn in row]
        assert len(all_buttons) == 3

    def test_keyboard_callbacks(self) -> None:
        rows = AdminEscalationService.build_admin_keyboard(12345)
        all_callbacks = [btn[1] for row in rows for btn in row]
        assert "agentesc:write:12345" in all_callbacks
        assert "agentesc:contacted:12345" in all_callbacks
        assert "agentesc:stop:12345" in all_callbacks


# ── mark_escalated ────────────────────────────────────────────────────────


class TestMarkEscalated:
    @pytest.mark.asyncio
    async def test_mark_escalated(self, mock_session: AsyncMock) -> None:
        svc = AdminEscalationService(mock_session)
        await svc.mark_escalated(12345, "followup_count=3")
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()


# ── No regression ─────────────────────────────────────────────────────────


class TestNoRegression:
    def test_catalog_buttons_unchanged(self) -> None:
        from core.services.followup_scheduler_service import FollowupSchedulerService
        _, buttons = FollowupSchedulerService.build_message("catalog")
        assert len(buttons) == 3

    def test_price_buttons_unchanged(self) -> None:
        from core.services.followup_scheduler_service import FollowupSchedulerService
        _, buttons = FollowupSchedulerService.build_message("price")
        assert len(buttons) == 3

    def test_order_buttons_unchanged(self) -> None:
        from core.services.followup_scheduler_service import FollowupSchedulerService
        _, buttons = FollowupSchedulerService.build_message("abandoned_order")
        assert len(buttons) == 3
