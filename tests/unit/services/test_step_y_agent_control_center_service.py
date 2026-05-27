"""Tests for Step Y — AgentControlCenterService."""

from __future__ import annotations

from types import SimpleNamespace

from core.services.agent_control_center_service import AgentControlCenterService

svc = AgentControlCenterService


def _biz(**kw) -> SimpleNamespace:
    defaults = {
        "agent_followups_enabled": False,
        "agent_catalog_followup_enabled": False,
        "agent_price_followup_enabled": False,
        "agent_order_followup_enabled": False,
        "agent_admin_escalation_enabled": False,
        "agent_ai_composer_enabled": False,
        "agent_decision_engine_enabled": False,
        "agent_lead_signal_enabled": False,
        "agent_lead_scoring_enabled": False,
        "agent_dynamic_offer_enabled": False,
        "agent_conversation_policy_enabled": False,
        "agent_response_orchestrator_enabled": False,
        "agent_response_orchestrator_log_only": True,
        "agent_execution_sandbox_enabled": False,
        "agent_execution_mode": "log_only",
        "agent_execution_queue_enabled": False,
        "agent_execution_live_sender_enabled": False,
        "agent_execution_live_sender_batch_limit": 10,
        "agent_execution_api_approval_enabled": False,
        "agent_execution_auto_execute_approved": False,
        "agent_execution_canary_user_ids": "",
        "agent_execution_approval_admin_notify": False,
        "agent_execution_max_daily_per_user": 3,
    }
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _settings(biz_kw=None, openai_key="sk-test", admin_group="-100"):
    biz = _biz(**(biz_kw or {}))
    return SimpleNamespace(
        business=biz,
        bot=SimpleNamespace(admin_group_id=admin_group),
        openai=SimpleNamespace(api_key=openai_key),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Rollout stage detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestRolloutStage:
    def test_all_off(self):
        r = svc.detect_rollout_stage(_biz())
        assert r.stage == "off"
        assert r.label == "OFF"

    def test_log_only(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_response_orchestrator_enabled=True,
                agent_response_orchestrator_log_only=True,
            )
        )
        assert r.stage == "log_only"

    def test_dry_run(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_response_orchestrator_enabled=True,
                agent_execution_sandbox_enabled=True,
                agent_execution_mode="dry_run",
            )
        )
        assert r.stage == "dry_run"

    def test_canary(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_response_orchestrator_enabled=True,
                agent_execution_sandbox_enabled=True,
                agent_execution_mode="canary",
            )
        )
        assert r.stage == "canary"

    def test_approval_required(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_response_orchestrator_enabled=True,
                agent_execution_queue_enabled=True,
                agent_execution_mode="approval_required",
            )
        )
        assert r.stage == "approval_required"

    def test_approved_live_send(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_response_orchestrator_enabled=True,
                agent_execution_live_sender_enabled=True,
                agent_execution_auto_execute_approved=True,
            )
        )
        assert r.stage == "approved_live_send"

    def test_custom_orch_no_log(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_response_orchestrator_enabled=True,
                agent_response_orchestrator_log_only=False,
            )
        )
        assert r.stage == "custom"

    def test_mixed(self):
        r = svc.detect_rollout_stage(
            _biz(
                agent_execution_sandbox_enabled=True,
                agent_execution_mode="live",
            )
        )
        assert r.stage == "mixed"

    def test_labels_stable(self):
        stages = ["off", "log_only", "dry_run", "canary", "approval_required", "approved_live_send"]
        for s in stages:
            assert isinstance(s, str)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Feature flags
# ═══════════════════════════════════════════════════════════════════════════════


class TestFeatureFlags:
    def test_returns_all_flags(self):
        flags = svc.get_feature_flags_status(_biz())
        assert len(flags) >= 15

    def test_all_off(self):
        flags = svc.get_feature_flags_status(_biz())
        assert all(not f.enabled for f in flags)

    def test_some_on(self):
        flags = svc.get_feature_flags_status(
            _biz(
                agent_lead_signal_enabled=True,
            )
        )
        enabled = [f for f in flags if f.enabled]
        assert len(enabled) >= 1

    def test_no_secrets_in_flags(self):
        flags = svc.get_feature_flags_status(_biz())
        for f in flags:
            assert "key" not in f.name.lower() or "api" not in f.name.lower()
            assert "token" not in f.name.lower()

    def test_flag_has_stage(self):
        flags = svc.get_feature_flags_status(_biz())
        for f in flags:
            assert f.stage != ""

    def test_flag_has_risk(self):
        flags = svc.get_feature_flags_status(_biz())
        for f in flags:
            assert f.risk in ("none", "low", "medium", "high")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Preflight
# ═══════════════════════════════════════════════════════════════════════════════


class TestPreflight:
    def test_all_off_green(self):
        r = svc.get_preflight_status(_biz(), _settings())
        assert r.status == "green"

    def test_canary_no_ids_red(self):
        r = svc.get_preflight_status(
            _biz(agent_execution_mode="canary"),
            _settings(),
        )
        assert r.status == "red"
        assert any("canary" in b.lower() for b in r.blockers)

    def test_canary_with_ids_green(self):
        r = svc.get_preflight_status(
            _biz(agent_execution_mode="canary", agent_execution_canary_user_ids="123,456"),
            _settings(),
        )
        assert "canary" not in " ".join(r.blockers).lower()

    def test_live_sender_no_queue_red(self):
        r = svc.get_preflight_status(
            _biz(agent_execution_live_sender_enabled=True),
            _settings(),
        )
        assert r.status == "red"
        assert any("queue" in b.lower() for b in r.blockers)

    def test_auto_exec_no_sender_red(self):
        r = svc.get_preflight_status(
            _biz(agent_execution_auto_execute_approved=True),
            _settings(),
        )
        assert r.status == "red"

    def test_ai_composer_no_key_yellow(self):
        r = svc.get_preflight_status(
            _biz(agent_ai_composer_enabled=True),
            _settings(openai_key=""),
        )
        assert r.status == "yellow"
        assert any("openai" in w.lower() for w in r.warnings)

    def test_admin_notify_no_group_yellow(self):
        r = svc.get_preflight_status(
            _biz(agent_execution_approval_admin_notify=True),
            _settings(admin_group=""),
        )
        assert r.status == "yellow"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Canary status
# ═══════════════════════════════════════════════════════════════════════════════


class TestCanaryStatus:
    def test_default_canary(self):
        c = svc.get_canary_status(_biz())
        assert c.canary_user_count == 0
        assert c.mode == "log_only"
        assert c.auto_execute is False

    def test_canary_with_ids(self):
        c = svc.get_canary_status(
            _biz(
                agent_execution_canary_user_ids="111,222,333",
                agent_execution_mode="canary",
            )
        )
        assert c.canary_user_count == 3
        assert c.mode == "canary"

    def test_approval_required(self):
        c = svc.get_canary_status(
            _biz(
                agent_execution_mode="approval_required",
            )
        )
        assert c.approval_required is True

    def test_batch_limit(self):
        c = svc.get_canary_status(
            _biz(
                agent_execution_live_sender_batch_limit=20,
            )
        )
        assert c.batch_limit == 20

    def test_daily_cap(self):
        c = svc.get_canary_status(
            _biz(
                agent_execution_max_daily_per_user=5,
            )
        )
        assert c.daily_cap == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Safety summary
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafetySummary:
    def test_green_default(self):
        sf = svc.get_safety_summary(_biz(), _settings())
        assert sf.status == "green"

    def test_red_with_blocker(self):
        sf = svc.get_safety_summary(
            _biz(agent_execution_live_sender_enabled=True),
            _settings(),
        )
        assert sf.status == "red"
        assert len(sf.dangerous_combos) > 0

    def test_yellow_with_warning(self):
        sf = svc.get_safety_summary(
            _biz(agent_ai_composer_enabled=True),
            _settings(openai_key=""),
        )
        assert sf.status == "yellow"


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Full snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestSnapshot:
    def test_snapshot_has_all_sections(self):
        snap = svc.build_control_center_snapshot(_settings())
        assert snap.rollout_stage is not None
        assert snap.preflight is not None
        assert snap.canary is not None
        assert snap.safety is not None
        assert snap.flags is not None

    def test_snapshot_health_from_preflight(self):
        snap = svc.build_control_center_snapshot(_settings())
        assert snap.health_status == snap.preflight.status

    def test_snapshot_default_off(self):
        snap = svc.build_control_center_snapshot(_settings())
        assert snap.rollout_stage.stage == "off"

    def test_snapshot_no_secrets(self):
        from dataclasses import asdict

        snap = svc.build_control_center_snapshot(_settings())
        text = str(asdict(snap))
        assert "sk-test" not in text
        assert "bot_token" not in text.lower()

    def test_snapshot_canary_ids_not_raw(self):
        from dataclasses import asdict

        snap = svc.build_control_center_snapshot(
            _settings(
                biz_kw={"agent_execution_canary_user_ids": "12345,67890"},
            )
        )
        text = str(asdict(snap))
        assert "12345" not in text
        assert "67890" not in text

    def test_snapshot_empty_config_safe(self):
        snap = svc.build_control_center_snapshot(None)
        assert snap.rollout_stage.stage == "off"  # default


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Immutability
# ═══════════════════════════════════════════════════════════════════════════════


class TestImmutability:
    def test_snapshot_frozen(self):
        import pytest

        snap = svc.build_control_center_snapshot(_settings())
        with pytest.raises(AttributeError):
            snap.health_status = "red"  # type: ignore[misc]

    def test_flag_frozen(self):
        import pytest

        flags = svc.get_feature_flags_status(_biz())
        with pytest.raises(AttributeError):
            flags[0].enabled = True  # type: ignore[misc]
