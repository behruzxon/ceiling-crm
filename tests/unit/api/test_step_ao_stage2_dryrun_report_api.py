"""Tests for Step AO — Stage 2 DRY_RUN Report API."""
from __future__ import annotations

from dataclasses import asdict
from core.schemas.stage2_dryrun_report import Stage2DryRunReport


class TestEndpoint:
    def test_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("stage2-dryrun-report" in p for p in paths)

    def test_auth(self):
        from apps.api.routes.admin_agent_observation import router
        assert len(router.dependencies) > 0

class TestResponse:
    def test_serializable(self):
        d = asdict(Stage2DryRunReport())
        assert "pass_fail" in d
        assert "no_send" in d
        assert "recommendations" in d
        assert "block_reason_counts" in d

    def test_no_secrets(self):
        text = str(asdict(Stage2DryRunReport()))
        assert "sk-" not in text and "+998" not in text

    def test_pass_fail_present(self):
        d = asdict(Stage2DryRunReport())
        assert d["pass_fail"]["passed"] is True

class TestNonRegression:
    def test_stage1_report_exists(self):
        from apps.api.main import create_app
        paths = [r.path for r in create_app().routes]
        assert any("stage1-report" in p for p in paths)

    def test_gate_exists(self):
        from apps.api.main import create_app
        paths = [r.path for r in create_app().routes]
        assert any("dryrun-gate" in p for p in paths)

    def test_signal_works(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
