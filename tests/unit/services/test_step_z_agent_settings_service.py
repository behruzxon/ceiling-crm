"""Tests for Step Z — AgentSettingsService (pure validation logic)."""

from __future__ import annotations

from core.services.agent_settings_service import AgentSettingsService

svc = AgentSettingsService


class TestAllowedKeys:
    def test_known_key_allowed(self):
        assert svc.is_allowed_key("agent_followups_enabled") is True

    def test_unknown_key_rejected(self):
        assert svc.is_allowed_key("agent_secret_key") is False

    def test_random_key_rejected(self):
        assert svc.is_allowed_key("random_thing") is False

    def test_execution_mode_allowed(self):
        assert svc.is_allowed_key("agent_execution_mode") is True

    def test_delay_minutes_allowed(self):
        assert svc.is_allowed_key("agent_catalog_followup_delay_minutes") is True


class TestValueValidation:
    def test_bool_flag_accepts_bool(self):
        ok, _ = svc.validate_value("agent_followups_enabled", True)
        assert ok is True

    def test_bool_flag_rejects_string(self):
        ok, _ = svc.validate_value("agent_followups_enabled", "yes")
        assert ok is False

    def test_int_flag_accepts_int(self):
        ok, _ = svc.validate_value("agent_catalog_followup_delay_minutes", 10)
        assert ok is True

    def test_int_flag_rejects_negative(self):
        ok, _ = svc.validate_value("agent_catalog_followup_delay_minutes", -1)
        assert ok is False

    def test_execution_mode_valid(self):
        ok, _ = svc.validate_value("agent_execution_mode", "canary")
        assert ok is True

    def test_execution_mode_invalid(self):
        ok, _ = svc.validate_value("agent_execution_mode", "turbo")
        assert ok is False


class TestRiskCalculation:
    def test_low_risk_delay(self):
        assert svc.calculate_risk("agent_catalog_followup_delay_minutes", 10) == "low"

    def test_medium_risk_signal(self):
        assert svc.calculate_risk("agent_lead_signal_enabled", True) == "medium"

    def test_high_risk_followups(self):
        assert svc.calculate_risk("agent_followups_enabled", True) == "high"

    def test_critical_live_sender(self):
        assert svc.calculate_risk("agent_execution_live_sender_enabled", True) == "critical"

    def test_critical_auto_execute(self):
        assert svc.calculate_risk("agent_execution_auto_execute_approved", True) == "critical"

    def test_critical_mode_live(self):
        assert svc.calculate_risk("agent_execution_mode", "live") == "critical"

    def test_high_risk_log_only_false(self):
        assert svc.calculate_risk("agent_response_orchestrator_log_only", False) == "high"

    def test_disabling_flag_low_risk(self):
        assert svc.calculate_risk("agent_followups_enabled", False) == "low"

    def test_disabling_critical_flag_low(self):
        assert svc.calculate_risk("agent_execution_live_sender_enabled", False) == "low"


class TestValidateChange:
    def test_unknown_key_blocked(self):
        r = svc.validate_change("unknown_flag", True)
        assert r.allowed is False
        assert any("unknown" in b for b in r.blockers)

    def test_low_risk_allowed(self):
        r = svc.validate_change("agent_catalog_followup_delay_minutes", 5)
        assert r.allowed is True

    def test_medium_risk_requires_confirmation(self):
        r = svc.validate_change("agent_lead_signal_enabled", True)
        assert r.allowed is True
        assert r.requires_confirmation is True

    def test_high_risk_requires_confirmation(self):
        r = svc.validate_change("agent_followups_enabled", True)
        assert r.allowed is True
        assert r.requires_confirmation is True

    def test_critical_blocked_default(self):
        r = svc.validate_change("agent_execution_live_sender_enabled", True)
        assert r.allowed is False
        assert any("critical" in b for b in r.blockers)

    def test_critical_allowed_with_flag(self):
        r = svc.validate_change(
            "agent_execution_live_sender_enabled",
            True,
            current_settings={"agent_execution_queue_enabled": True},
            allow_live_flags=True,
        )
        assert r.allowed is True

    def test_live_sender_without_queue_blocked(self):
        r = svc.validate_change(
            "agent_execution_live_sender_enabled",
            True,
            current_settings={"agent_execution_queue_enabled": False},
            allow_live_flags=True,
        )
        assert r.allowed is False
        assert any("queue" in b for b in r.blockers)

    def test_auto_execute_without_sender_blocked(self):
        r = svc.validate_change(
            "agent_execution_auto_execute_approved",
            True,
            current_settings={"agent_execution_live_sender_enabled": False},
            allow_live_flags=True,
        )
        assert r.allowed is False

    def test_canary_without_ids_blocked(self):
        r = svc.validate_change(
            "agent_execution_mode",
            "canary",
            current_settings={"agent_execution_canary_user_ids": ""},
        )
        assert r.allowed is False
        assert any("canary" in b for b in r.blockers)

    def test_canary_with_ids_allowed(self):
        r = svc.validate_change(
            "agent_execution_mode",
            "canary",
            current_settings={"agent_execution_canary_user_ids": "123,456"},
        )
        assert r.allowed is True

    def test_live_mode_blocked_default(self):
        r = svc.validate_change("agent_execution_mode", "live")
        assert r.allowed is False

    def test_live_mode_allowed_with_flag(self):
        r = svc.validate_change(
            "agent_execution_mode",
            "live",
            allow_live_flags=True,
        )
        assert r.allowed is True

    def test_dry_run_allowed(self):
        r = svc.validate_change("agent_execution_mode", "dry_run")
        assert r.allowed is True

    def test_log_only_allowed(self):
        r = svc.validate_change("agent_execution_mode", "log_only")
        assert r.allowed is True

    def test_all_off_safe(self):
        r = svc.validate_change("agent_followups_enabled", False)
        assert r.allowed is True

    def test_disabling_is_low_risk(self):
        r = svc.validate_change("agent_execution_live_sender_enabled", False)
        assert r.allowed is True
        assert r.risk_level == "low"

    def test_confirmation_token_generated(self):
        r = svc.validate_change("agent_lead_signal_enabled", True)
        assert r.confirmation_token is not None
        assert len(r.confirmation_token) == 24

    def test_token_not_raw_key(self):
        r = svc.validate_change("agent_followups_enabled", True)
        assert "agent_followups" not in (r.confirmation_token or "")


class TestConfirmationToken:
    def test_generate_token(self):
        t = svc.generate_confirmation_token("key", True)
        assert len(t) == 24

    def test_tokens_unique(self):
        t1 = svc.generate_confirmation_token("key", True)
        t2 = svc.generate_confirmation_token("key", True)
        assert t1 != t2

    def test_verify_valid_token(self):
        t = svc.generate_confirmation_token("key", True)
        assert svc.verify_confirmation_token(t) is True

    def test_verify_empty_token_fails(self):
        assert svc.verify_confirmation_token("") is False

    def test_verify_short_token_fails(self):
        assert svc.verify_confirmation_token("abc") is False


class TestDangerousCombinations:
    def test_no_dangers_default(self):
        d = svc.detect_dangerous_combinations({})
        assert d == []

    def test_live_sender_without_queue(self):
        d = svc.detect_dangerous_combinations(
            {
                "agent_execution_live_sender_enabled": True,
            }
        )
        assert "live_sender_without_queue" in d

    def test_auto_execute_without_sender(self):
        d = svc.detect_dangerous_combinations(
            {
                "agent_execution_auto_execute_approved": True,
            }
        )
        assert "auto_execute_without_sender" in d

    def test_canary_without_ids(self):
        d = svc.detect_dangerous_combinations(
            {
                "agent_execution_mode": "canary",
                "agent_execution_canary_user_ids": "",
            }
        )
        assert "canary_without_user_ids" in d

    def test_live_mode_dangerous(self):
        d = svc.detect_dangerous_combinations(
            {
                "agent_execution_mode": "live",
            }
        )
        assert "execution_mode_live" in d

    def test_safe_config_no_dangers(self):
        d = svc.detect_dangerous_combinations(
            {
                "agent_execution_queue_enabled": True,
                "agent_execution_live_sender_enabled": True,
                "agent_execution_auto_execute_approved": True,
                "agent_execution_mode": "approval_required",
            }
        )
        assert "live_sender_without_queue" not in d
        assert "auto_execute_without_sender" not in d


class TestSanitizeForAPI:
    def test_returns_list(self):
        r = svc.sanitize_settings_for_api({"agent_followups_enabled": False})
        assert isinstance(r, list)

    def test_no_unknown_keys(self):
        r = svc.sanitize_settings_for_api({"unknown": True, "agent_followups_enabled": False})
        keys = [s.key for s in r]
        assert "unknown" not in keys

    def test_risk_level_included(self):
        r = svc.sanitize_settings_for_api({"agent_followups_enabled": True})
        assert r[0].risk_level == "high"


class TestRollbackSnapshot:
    def test_snapshot_captures_values(self):
        snap = svc.build_rollback_snapshot({"agent_followups_enabled": True})
        assert snap.get("agent_followups_enabled") is True

    def test_snapshot_excludes_unknown(self):
        snap = svc.build_rollback_snapshot({"unknown_key": True})
        assert "unknown_key" not in snap

    def test_snapshot_excludes_none(self):
        snap = svc.build_rollback_snapshot({"agent_followups_enabled": None})
        assert "agent_followups_enabled" not in snap


class TestImmutability:
    def test_validation_frozen(self):
        import pytest

        r = svc.validate_change("agent_followups_enabled", True)
        with pytest.raises(AttributeError):
            r.allowed = False  # type: ignore[misc]
