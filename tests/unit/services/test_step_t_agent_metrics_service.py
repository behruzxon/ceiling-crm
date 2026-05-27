"""Tests for Step T — AgentMetricsService."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.schemas.agent_metrics import (
    AdminEscalationMetrics,
    AgentHealthMetrics,
    AgentMetricsOverview,
    ExecutionMetrics,
    FollowupMetrics,
    JourneyMetrics,
    LeadMetrics,
    SafetyMetrics,
)
from core.services.agent_metrics_service import AgentMetricsService

svc = AgentMetricsService


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Health computation (pure, no DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthComputation:
    def test_green_empty(self):
        h = svc.compute_health()
        assert h.status == "green"
        assert h.warnings == []

    def test_green_normal(self):
        h = svc.compute_health(pending_due=5, failed_24h=2)
        assert h.status == "green"

    def test_yellow_pending_high(self):
        h = svc.compute_health(pending_due=25)
        assert h.status == "yellow"
        assert "pending_followups_high" in h.warnings

    def test_yellow_failed_elevated(self):
        h = svc.compute_health(failed_24h=8)
        assert h.status == "yellow"
        assert "failed_followups_elevated" in h.warnings

    def test_yellow_expired_approvals(self):
        h = svc.compute_health(expired_approvals=15)
        assert h.status == "yellow"
        assert "expired_approvals_high" in h.warnings

    def test_red_failed_critical(self):
        h = svc.compute_health(failed_24h=25)
        assert h.status == "red"
        assert "failed_followups_critical" in h.warnings

    def test_red_stale_followups(self):
        h = svc.compute_health(stale_followups=3)
        assert h.status == "red"
        assert "stale_followups_detected" in h.warnings

    def test_red_execution_failures(self):
        h = svc.compute_health(execution_failures=15)
        assert h.status == "red"
        assert "execution_failures_high" in h.warnings

    def test_red_overrides_yellow(self):
        h = svc.compute_health(
            pending_due=25, failed_24h=25,
        )
        assert h.status == "red"

    def test_multiple_yellow_warnings(self):
        h = svc.compute_health(pending_due=25, failed_24h=8)
        assert h.status == "yellow"
        assert len(h.warnings) == 2

    def test_boundary_pending_20_green(self):
        h = svc.compute_health(pending_due=20)
        assert h.status == "green"

    def test_boundary_pending_21_yellow(self):
        h = svc.compute_health(pending_due=21)
        assert h.status == "yellow"

    def test_boundary_failed_5_green(self):
        h = svc.compute_health(failed_24h=5)
        assert h.status == "green"

    def test_boundary_failed_6_yellow(self):
        h = svc.compute_health(failed_24h=6)
        assert h.status == "yellow"

    def test_boundary_failed_20_yellow(self):
        h = svc.compute_health(failed_24h=20)
        assert h.status == "yellow"

    def test_boundary_failed_21_red(self):
        h = svc.compute_health(failed_24h=21)
        assert h.status == "red"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Schema defaults (no DB)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaDefaults:
    def test_journey_defaults(self):
        j = JourneyMetrics()
        assert j.total_events == 0
        assert j.active_users == 0
        assert j.events_by_type == {}

    def test_lead_defaults(self):
        l = LeadMetrics()
        assert l.total_memories == 0
        assert l.hot_count == 0
        assert l.average_score == 0.0

    def test_followup_defaults(self):
        f = FollowupMetrics()
        assert f.total == 0
        assert f.pending == 0
        assert f.due_count == 0

    def test_escalation_defaults(self):
        e = AdminEscalationMetrics()
        assert e.total == 0
        assert e.last_24h == 0

    def test_execution_defaults(self):
        e = ExecutionMetrics()
        assert e.total == 0
        assert e.by_status == {}
        assert e.pending_approval == 0

    def test_safety_defaults(self):
        s = SafetyMetrics()
        assert s.stop_signals == 0
        assert s.sandbox_blocked == 0

    def test_health_defaults(self):
        h = AgentHealthMetrics()
        assert h.status == "green"
        assert h.warnings == []

    def test_overview_defaults(self):
        o = AgentMetricsOverview()
        assert o.journey.total_events == 0
        assert o.health.status == "green"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Schema immutability
# ═══════════════════════════════════════════════════════════════════════════════


class TestImmutability:
    def test_journey_frozen(self):
        j = JourneyMetrics()
        with pytest.raises(AttributeError):
            j.total_events = 5  # type: ignore[misc]

    def test_health_frozen(self):
        h = AgentHealthMetrics()
        with pytest.raises(AttributeError):
            h.status = "red"  # type: ignore[misc]

    def test_overview_frozen(self):
        o = AgentMetricsOverview()
        with pytest.raises(AttributeError):
            o.journey = JourneyMetrics(total_events=5)  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Service with mocked session — journey metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestJourneyMetrics:
    async def test_empty_db_returns_zeros(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])),
        )
        s = AgentMetricsService(session)
        j = await s.get_journey_metrics()
        assert j.total_events == 0
        assert j.active_users == 0

    async def test_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        s = AgentMetricsService(session)
        j = await s.get_journey_metrics()
        assert j.total_events == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Service with mocked session — lead metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestLeadMetrics:
    async def test_empty_db_returns_zeros(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])),
        )
        s = AgentMetricsService(session)
        l = await s.get_lead_metrics()
        assert l.total_memories == 0
        assert l.hot_count == 0

    async def test_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        s = AgentMetricsService(session)
        l = await s.get_lead_metrics()
        assert l.total_memories == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Followup metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestFollowupMetrics:
    async def test_empty_db(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])),
        )
        s = AgentMetricsService(session)
        f = await s.get_followup_metrics()
        assert f.total == 0
        assert f.due_count == 0

    async def test_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        s = AgentMetricsService(session)
        f = await s.get_followup_metrics()
        assert f.total == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Execution metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionMetrics:
    async def test_empty_db(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[])),
        )
        s = AgentMetricsService(session)
        e = await s.get_execution_metrics()
        assert e.total == 0
        assert e.pending_approval == 0

    async def test_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        s = AgentMetricsService(session)
        e = await s.get_execution_metrics()
        assert e.total == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Safety metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafetyMetrics:
    async def test_empty_db(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = AgentMetricsService(session)
        sf = await s.get_safety_metrics()
        assert sf.stop_signals == 0
        assert sf.sandbox_blocked == 0

    async def test_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        s = AgentMetricsService(session)
        sf = await s.get_safety_metrics()
        assert sf.stop_signals == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Admin escalation metrics
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminEscalationMetrics:
    async def test_empty_db(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = AgentMetricsService(session)
        e = await s.get_admin_escalation_metrics()
        assert e.total == 0
        assert e.last_24h == 0

    async def test_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        s = AgentMetricsService(session)
        e = await s.get_admin_escalation_metrics()
        assert e.total == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Overview integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestOverview:
    async def test_overview_returns_all_sections(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        s = AgentMetricsService(session)
        o = await s.get_overview()
        assert o.journey is not None
        assert o.leads is not None
        assert o.followups is not None
        assert o.escalations is not None
        assert o.executions is not None
        assert o.safety is not None
        assert o.health is not None
        assert o.health.status == "green"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. DI + imports
# ═══════════════════════════════════════════════════════════════════════════════


class TestDI:
    def test_di_importable(self):
        from infrastructure.di import get_agent_metrics_service
        assert callable(get_agent_metrics_service)

    def test_service_importable(self):
        from core.services.agent_metrics_service import AgentMetricsService
        assert AgentMetricsService is not None

    def test_schemas_importable(self):
        from core.schemas.agent_metrics import AgentMetricsOverview
        assert AgentMetricsOverview is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Safety: read-only, no mutations
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadOnly:
    async def test_no_add_called(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        s = AgentMetricsService(session)
        await s.get_overview()
        session.add.assert_not_called()

    async def test_no_flush_called(self):
        session = AsyncMock()
        session.flush = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        s = AgentMetricsService(session)
        await s.get_overview()
        session.flush.assert_not_called()

    async def test_no_commit_called(self):
        session = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        s = AgentMetricsService(session)
        await s.get_overview()
        session.commit.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Metrics with data
# ═══════════════════════════════════════════════════════════════════════════════


class TestWithData:
    def test_health_multiple_issues(self):
        h = svc.compute_health(
            pending_due=30, failed_24h=25, expired_approvals=15,
            execution_failures=12, stale_followups=2,
        )
        assert h.status == "red"
        assert len(h.warnings) >= 2

    def test_health_stores_values(self):
        h = svc.compute_health(
            pending_due=5, failed_24h=3,
            expired_approvals=2, execution_failures=1,
        )
        assert h.pending_followups_due == 5
        assert h.failed_followups_24h == 3
        assert h.expired_approvals == 2
        assert h.execution_failures == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 14. Schema construction with data
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaWithData:
    def test_journey_with_events(self):
        j = JourneyMetrics(
            total_events=100,
            events_by_type={"opened_catalog": 30, "price_calculated": 20},
            active_users=50,
            catalog_opened=30,
            price_calculated=20,
        )
        assert j.total_events == 100
        assert j.catalog_opened == 30

    def test_lead_with_temps(self):
        l = LeadMetrics(
            total_memories=100, hot_count=20, warm_count=50, cold_count=30,
        )
        assert l.hot_count + l.warm_count + l.cold_count == 100

    def test_followup_with_statuses(self):
        f = FollowupMetrics(
            total=50, pending=10, sent=30, cancelled=5, failed=3, skipped=2,
        )
        assert f.total == 50
        assert f.pending == 10

    def test_execution_with_statuses(self):
        e = ExecutionMetrics(
            total=20,
            by_status={"proposed": 5, "approved": 3, "executed": 10, "rejected": 2},
            pending_approval=5,
        )
        assert e.pending_approval == 5
        assert sum(e.by_status.values()) == 20

    def test_safety_with_data(self):
        s = SafetyMetrics(stop_signals=15, sandbox_blocked=8)
        assert s.stop_signals == 15

    def test_escalation_with_data(self):
        e = AdminEscalationMetrics(total=50, last_24h=5)
        assert e.last_24h == 5

    def test_overview_with_red_health(self):
        h = AgentHealthMetrics(status="red", warnings=["critical"])
        o = AgentMetricsOverview(health=h)
        assert o.health.status == "red"


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Health edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthEdgeCases:
    def test_all_zeros_green(self):
        h = svc.compute_health(
            pending_due=0, failed_24h=0,
            expired_approvals=0, execution_failures=0,
            stale_followups=0,
        )
        assert h.status == "green"

    def test_one_stale_is_red(self):
        h = svc.compute_health(stale_followups=1)
        assert h.status == "red"

    def test_exactly_10_expired_green(self):
        h = svc.compute_health(expired_approvals=10)
        assert h.status == "green"

    def test_exactly_11_expired_yellow(self):
        h = svc.compute_health(expired_approvals=11)
        assert h.status == "yellow"

    def test_exactly_10_exec_failures_yellow(self):
        h = svc.compute_health(execution_failures=10)
        assert h.status == "green"

    def test_exactly_11_exec_failures_red(self):
        h = svc.compute_health(execution_failures=11)
        assert h.status == "red"

    def test_large_numbers_red(self):
        h = svc.compute_health(
            pending_due=1000, failed_24h=500,
            expired_approvals=200, execution_failures=100,
            stale_followups=50,
        )
        assert h.status == "red"
        assert len(h.warnings) >= 2

    def test_warnings_list_not_shared(self):
        h1 = svc.compute_health(pending_due=25)
        h2 = svc.compute_health()
        assert h1.warnings != h2.warnings


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Non-regression
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonRegression:
    def test_sandbox_still_works(self):
        from core.services.agent_execution_sandbox_service import (
            AgentExecutionSandboxService,
        )
        assert AgentExecutionSandboxService is not None

    def test_orchestrator_still_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )
        mem = {"followup_enabled": True, "memory_data": {},
               "lead_temperature": "warm", "telegram_user_id": 1}
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"

    def test_signal_service_still_works(self):
        from core.services.lead_signal_service import LeadSignalService
        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"

    def test_policy_still_works(self):
        from core.services.conversation_policy_service import (
            ConversationPolicyService,
        )
        p = ConversationPolicyService.evaluate(
            {"followup_enabled": True, "lead_temperature": "warm",
             "memory_data": {"last_intent": "wants_price"}},
        )
        assert p.policy_action == "reply_now"

    def test_offer_still_works(self):
        from core.services.dynamic_offer_service import DynamicOfferService
        o = DynamicOfferService.choose_offer(
            {"lead_temperature": "warm", "memory_data": {"last_intent": "wants_price"}},
        )
        assert o.offer_type == "price_calculation"

    def test_normalization_still_works(self):
        from core.services.text_normalization_service import (
            TextNormalizationService,
        )
        r = TextNormalizationService.normalize("нархи қанча")
        assert "narxi" in r.latin

    def test_queue_still_works(self):
        from core.services.agent_execution_queue_service import (
            AgentExecutionQueueService,
        )
        assert callable(AgentExecutionQueueService.can_execute)
