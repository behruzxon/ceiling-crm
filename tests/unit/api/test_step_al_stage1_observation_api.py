"""Tests for Step AL — Stage 1 Observation Report API."""

from __future__ import annotations


class TestEndpoint:
    def test_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("stage1-report" in p for p in paths)

    def test_router_has_auth(self):
        from apps.api.routes.admin_agent_observation import router

        assert len(router.dependencies) > 0

    def test_router_prefix(self):
        from apps.api.routes.admin_agent_observation import router

        assert "observation" in router.prefix


class TestResponseShape:
    def test_report_serializable(self):
        from dataclasses import asdict

        from core.schemas.stage1_observation_report import Stage1ObservationReport

        r = Stage1ObservationReport()
        d = asdict(r)
        assert "pass_fail" in d
        assert "no_send" in d
        assert "recommendations" in d

    def test_no_phone_in_default(self):
        from dataclasses import asdict

        from core.schemas.stage1_observation_report import Stage1ObservationReport

        text = str(asdict(Stage1ObservationReport()))
        assert "+998" not in text

    def test_no_token_in_default(self):
        from dataclasses import asdict

        from core.schemas.stage1_observation_report import Stage1ObservationReport

        text = str(asdict(Stage1ObservationReport()))
        assert "sk-" not in text

    def test_pass_fail_present(self):
        from dataclasses import asdict

        from core.schemas.stage1_observation_report import Stage1ObservationReport

        d = asdict(Stage1ObservationReport())
        assert d["pass_fail"]["passed"] is True

    def test_no_send_present(self):
        from dataclasses import asdict

        from core.schemas.stage1_observation_report import Stage1ObservationReport

        d = asdict(Stage1ObservationReport())
        assert d["no_send"]["followups_sent"] == 0

    def test_recommendations_present(self):
        from dataclasses import asdict

        from core.schemas.stage1_observation_report import Stage1ObservationReport

        d = asdict(Stage1ObservationReport())
        assert isinstance(d["recommendations"], list)


class TestNonRegression:
    def test_metrics_endpoint_still_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("metrics/overview" in p for p in paths)

    def test_control_status_still_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("control/status" in p for p in paths)

    def test_signal_still_works(self):
        from core.services.lead_signal_service import LeadSignalService

        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"
