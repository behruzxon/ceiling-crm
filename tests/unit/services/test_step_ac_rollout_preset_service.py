"""Tests for Step AC — AgentRolloutPresetService."""
from __future__ import annotations

from core.services.agent_rollout_preset_service import AgentRolloutPresetService

svc = AgentRolloutPresetService


class TestListPresets:
    def test_returns_6(self):
        assert len(svc.list_presets()) == 6

    def test_names(self):
        names = [p.name for p in svc.list_presets()]
        assert "off" in names
        assert "log_only" in names
        assert "dry_run" in names
        assert "canary" in names
        assert "approval_required" in names
        assert "approved_live_send" in names

    def test_all_have_labels(self):
        for p in svc.list_presets():
            assert p.label
            assert p.description

    def test_all_have_risk(self):
        for p in svc.list_presets():
            assert p.risk_level in ("low", "medium", "high", "critical")


class TestGetPreset:
    def test_known(self):
        assert svc.get_preset("off") is not None

    def test_unknown_none(self):
        assert svc.get_preset("turbo") is None

    def test_case_insensitive(self):
        assert svc.get_preset("LOG_ONLY") is not None


class TestBuildSettings:
    def test_off_all_false(self):
        s = svc.build_preset_settings("off")
        assert s is not None
        assert s["agent_followups_enabled"] is False
        assert s["agent_execution_live_sender_enabled"] is False

    def test_log_only_flags(self):
        s = svc.build_preset_settings("log_only")
        assert s["agent_lead_signal_enabled"] is True
        assert s["agent_response_orchestrator_enabled"] is True
        assert s["agent_response_orchestrator_log_only"] is True
        assert s["agent_followups_enabled"] is False

    def test_dry_run_flags(self):
        s = svc.build_preset_settings("dry_run")
        assert s["agent_execution_sandbox_enabled"] is True
        assert s["agent_execution_mode"] == "dry_run"

    def test_canary_mode(self):
        s = svc.build_preset_settings("canary")
        assert s["agent_execution_mode"] == "canary"
        assert s["agent_followups_enabled"] is True

    def test_approval_flags(self):
        s = svc.build_preset_settings("approval_required")
        assert s["agent_execution_queue_enabled"] is True
        assert s["agent_execution_api_approval_enabled"] is True
        assert s["agent_execution_auto_execute_approved"] is False

    def test_live_send_flags(self):
        s = svc.build_preset_settings("approved_live_send")
        assert s["agent_execution_live_sender_enabled"] is True
        assert s["agent_execution_auto_execute_approved"] is True
        assert s["agent_execution_queue_enabled"] is True

    def test_unknown_none(self):
        assert svc.build_preset_settings("unknown") is None


class TestDiffSettings:
    def test_detects_changes(self):
        current = {"agent_followups_enabled": False}
        target = {"agent_followups_enabled": True}
        diff = svc.diff_settings(current, target)
        assert len(diff) == 1
        assert diff[0].key == "agent_followups_enabled"
        assert diff[0].target_value is True

    def test_no_diff_same(self):
        s = {"agent_followups_enabled": False}
        diff = svc.diff_settings(s, s)
        assert len(diff) == 0

    def test_multiple_diffs(self):
        current = {"a": False, "b": False, "c": True}
        target = {"a": True, "b": True, "c": True}
        diff = svc.diff_settings(current, target)
        assert len(diff) == 2

    def test_diff_has_risk(self):
        diff = svc.diff_settings(
            {"agent_followups_enabled": False},
            {"agent_followups_enabled": True},
        )
        assert diff[0].risk_level


class TestRisk:
    def test_off_low(self):
        assert svc.calculate_preset_risk("off") == "low"

    def test_log_only_medium(self):
        assert svc.calculate_preset_risk("log_only") == "medium"

    def test_dry_run_medium(self):
        assert svc.calculate_preset_risk("dry_run") == "medium"

    def test_canary_high(self):
        assert svc.calculate_preset_risk("canary") == "high"

    def test_approval_high(self):
        assert svc.calculate_preset_risk("approval_required") == "high"

    def test_live_send_critical(self):
        assert svc.calculate_preset_risk("approved_live_send") == "critical"

    def test_unknown_none(self):
        assert svc.calculate_preset_risk("unknown") == "none"


class TestBlockers:
    def test_canary_no_ids(self):
        b = svc.detect_blockers("canary", {})
        assert "canary_requires_user_ids" in b

    def test_canary_with_ids_ok(self):
        b = svc.detect_blockers("canary", {
            "agent_execution_canary_user_ids": "123",
        })
        assert not b

    def test_live_send_no_allow(self):
        b = svc.detect_blockers("approved_live_send", {})
        assert "live_send_requires_allow_live_flags" in b

    def test_live_send_with_allow(self):
        b = svc.detect_blockers("approved_live_send", {}, allow_live_flags=True)
        assert not b

    def test_off_no_blockers(self):
        b = svc.detect_blockers("off", {})
        assert not b

    def test_log_only_no_blockers(self):
        b = svc.detect_blockers("log_only", {})
        assert not b


class TestPreview:
    def test_unknown_rejected(self):
        r = svc.preview_preset("unknown")
        assert r.allowed is False
        assert any("unknown" in b for b in r.blockers)

    def test_off_allowed(self):
        r = svc.preview_preset("off")
        assert r.allowed is True

    def test_log_only_allowed(self):
        r = svc.preview_preset("log_only")
        assert r.allowed is True
        assert r.requires_confirmation is True

    def test_log_only_has_token(self):
        r = svc.preview_preset("log_only")
        assert r.confirmation_token is not None
        assert len(r.confirmation_token) == 24

    def test_canary_no_ids_blocked(self):
        r = svc.preview_preset("canary", {})
        assert r.allowed is False

    def test_canary_with_ids_allowed(self):
        r = svc.preview_preset("canary", {
            "agent_execution_canary_user_ids": "123,456",
        })
        assert r.allowed is True

    def test_live_send_blocked_default(self):
        r = svc.preview_preset("approved_live_send")
        assert r.allowed is False

    def test_live_send_allowed_with_flag(self):
        r = svc.preview_preset("approved_live_send", {}, allow_live_flags=True)
        assert r.allowed is True

    def test_off_diff(self):
        r = svc.preview_preset("off", {
            "agent_followups_enabled": True,
        })
        keys = [d.key for d in r.diff]
        assert "agent_followups_enabled" in keys

    def test_no_diff_already_off(self):
        off_settings = svc.build_preset_settings("off")
        r = svc.preview_preset("off", off_settings)
        assert len(r.diff) == 0

    def test_no_secret_in_preview(self):
        r = svc.preview_preset("log_only")
        text = str(r)
        assert "api_key" not in text.lower()


class TestImmutability:
    def test_preview_frozen(self):
        import pytest
        r = svc.preview_preset("off")
        with pytest.raises(AttributeError):
            r.allowed = False  # type: ignore[misc]

    def test_diff_frozen(self):
        import pytest
        from core.schemas.agent_rollout_preset import AgentRolloutPresetDiff
        d = AgentRolloutPresetDiff(key="k", current_value=False, target_value=True)
        with pytest.raises(AttributeError):
            d.key = "other"  # type: ignore[misc]


class TestNonRegression:
    def test_signal_works(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"

    def test_settings_service_works(self):
        from core.services.agent_settings_service import AgentSettingsService
        r = AgentSettingsService.validate_change("agent_followups_enabled", True)
        assert r.allowed is True

    def test_effective_settings_works(self):
        from core.services.agent_effective_settings_service import AgentEffectiveSettingsService
        s = AgentEffectiveSettingsService({})
        f = s.get_followup_settings()
        assert f.enabled is False
