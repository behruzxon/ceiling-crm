"""Tests for Step V — Agent Admin Dashboard API + service integration."""

from __future__ import annotations

from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock

from core.schemas.agent_metrics import (
    AgentHealthMetrics,
    AgentMetricsOverview,
    ExecutionMetrics,
    FollowupMetrics,
    JourneyMetrics,
    LeadMetrics,
    SafetyMetrics,
)
from core.services.agent_metrics_service import AgentMetricsService

# ═══════════════════════════════════════════════════════════════════════════════
# 1. API route importability
# ═══════════════════════════════════════════════════════════════════════════════


class TestAPIRouteImport:
    def test_router_importable(self):
        from apps.api.routes.admin_agent_metrics import router

        assert router is not None

    def test_router_has_prefix(self):
        from apps.api.routes.admin_agent_metrics import router

        assert router.prefix == "/api/v1/admin/agent"

    def test_router_has_tags(self):
        from apps.api.routes.admin_agent_metrics import router

        assert "agent-admin" in router.tags

    def test_app_includes_router(self):
        from apps.api.main import create_app

        app = create_app()
        routes = [r.path for r in app.routes]
        assert any("/admin/agent" in r for r in routes)

    def test_overview_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        routes = [r.path for r in app.routes]
        assert any("metrics/overview" in r for r in routes)

    def test_health_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        routes = [r.path for r in app.routes]
        assert any("metrics/health" in r for r in routes)

    def test_pending_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        routes = [r.path for r in app.routes]
        assert any("executions/pending" in r for r in routes)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Overview serialization
# ═══════════════════════════════════════════════════════════════════════════════


class TestOverviewSerialization:
    def test_overview_to_dict(self):
        o = AgentMetricsOverview()
        d = asdict(o)
        assert "journey" in d
        assert "leads" in d
        assert "followups" in d
        assert "health" in d

    def test_journey_to_dict(self):
        j = JourneyMetrics(total_events=100, active_users=50)
        d = asdict(j)
        assert d["total_events"] == 100
        assert d["active_users"] == 50

    def test_leads_to_dict(self):
        l = LeadMetrics(hot_count=10, warm_count=20, cold_count=30)
        d = asdict(l)
        assert d["hot_count"] == 10

    def test_followups_to_dict(self):
        f = FollowupMetrics(pending=5, sent=10, due_count=3)
        d = asdict(f)
        assert d["pending"] == 5
        assert d["due_count"] == 3

    def test_executions_to_dict(self):
        e = ExecutionMetrics(
            total=20,
            by_status={"proposed": 5, "executed": 10},
            pending_approval=5,
        )
        d = asdict(e)
        assert d["pending_approval"] == 5

    def test_safety_to_dict(self):
        s = SafetyMetrics(stop_signals=8, sandbox_blocked=3)
        d = asdict(s)
        assert d["stop_signals"] == 8

    def test_health_to_dict(self):
        h = AgentHealthMetrics(status="yellow", warnings=["test"])
        d = asdict(h)
        assert d["status"] == "yellow"
        assert "test" in d["warnings"]

    def test_full_overview_serializes_clean(self):
        o = AgentMetricsOverview(
            journey=JourneyMetrics(total_events=50),
            leads=LeadMetrics(hot_count=5),
            health=AgentHealthMetrics(status="green"),
        )
        d = asdict(o)
        assert d["journey"]["total_events"] == 50
        assert d["leads"]["hot_count"] == 5
        assert d["health"]["status"] == "green"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Empty DB safety
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptyDB:
    async def test_empty_overview_no_crash(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        svc = AgentMetricsService(session)
        o = await svc.get_overview()
        assert o.journey.total_events == 0
        assert o.health.status == "green"

    async def test_empty_execution_metrics(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(all=MagicMock(return_value=[])),
        )
        svc = AgentMetricsService(session)
        e = await svc.get_execution_metrics()
        assert e.total == 0
        assert e.pending_approval == 0

    async def test_empty_followup_metrics(self):
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        svc = AgentMetricsService(session)
        f = await svc.get_followup_metrics()
        assert f.total == 0

    async def test_db_exception_returns_defaults(self):
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB down"))
        svc = AgentMetricsService(session)
        o = await svc.get_overview()
        assert o.journey.total_events == 0
        assert o.health.status == "green"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. No secrets in serialized output
# ═══════════════════════════════════════════════════════════════════════════════


class TestNoSecrets:
    def test_overview_no_phone(self):
        o = AgentMetricsOverview()
        d = str(asdict(o))
        assert "+998" not in d

    def test_overview_no_token(self):
        o = AgentMetricsOverview()
        d = str(asdict(o))
        assert "sk-" not in d

    def test_health_no_secrets(self):
        h = AgentHealthMetrics(status="red", warnings=["test_warning"])
        d = str(asdict(h))
        assert "token" not in d.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Web template
# ═══════════════════════════════════════════════════════════════════════════════


class TestWebTemplate:
    def test_template_exists(self):
        from pathlib import Path

        tpl = Path("apps/web/templates/agent.html")
        assert tpl.exists()

    def test_base_template_has_agent_link(self):
        from pathlib import Path

        base = Path("apps/web/templates/base.html").read_text(encoding="utf-8")
        assert "/agent" in base

    def test_web_route_importable(self):
        from apps.web.main import app

        routes = [r.path for r in app.routes]
        assert "/agent" in routes


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Health computation consistency
# ═══════════════════════════════════════════════════════════════════════════════


class TestHealthConsistency:
    def test_green_serializes(self):
        h = AgentMetricsService.compute_health()
        d = asdict(h)
        assert d["status"] == "green"

    def test_yellow_serializes(self):
        h = AgentMetricsService.compute_health(pending_due=30)
        d = asdict(h)
        assert d["status"] == "yellow"
        assert len(d["warnings"]) > 0

    def test_red_serializes(self):
        h = AgentMetricsService.compute_health(failed_24h=25)
        d = asdict(h)
        assert d["status"] == "red"

    def test_health_in_overview(self):
        o = AgentMetricsOverview(
            health=AgentMetricsService.compute_health(stale_followups=1),
        )
        d = asdict(o)
        assert d["health"]["status"] == "red"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Read-only assertion
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadOnly:
    async def test_no_writes(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(
                scalar=MagicMock(return_value=0),
                all=MagicMock(return_value=[]),
            ),
        )
        svc = AgentMetricsService(session)
        await svc.get_overview()
        session.add.assert_not_called()
        session.flush.assert_not_called()
        session.commit.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Non-regression
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonRegression:
    def test_metrics_service_importable(self):
        from infrastructure.di import get_agent_metrics_service

        assert callable(get_agent_metrics_service)

    def test_signal_still_works(self):
        from core.services.lead_signal_service import LeadSignalService

        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"

    def test_orchestrator_still_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        mem = {
            "followup_enabled": True,
            "memory_data": {},
            "lead_temperature": "warm",
            "telegram_user_id": 1,
        }
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"
