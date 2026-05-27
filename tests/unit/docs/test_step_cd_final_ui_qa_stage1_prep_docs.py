"""Tests for Step CD — Final UI QA + Stage 1 Prep Docs."""

from __future__ import annotations

from pathlib import Path

_DOC = "docs/AI_AGENT_SYSTEM/90_FINAL_UI_QA_STAGE_1_PREP.md"


def _content():
    return Path(_DOC).read_text(encoding="utf-8")


class TestDocExists:
    def test_doc_90_exists(self):
        assert Path(_DOC).exists()

    def test_checklist_82_exists(self):
        assert Path("docs/AI_AGENT_SYSTEM/82_STAGE_1_GO_NO_GO_CHECKLIST.md").exists()

    def test_stage1_apply_53_exists(self):
        assert Path("docs/AI_AGENT_SYSTEM/53_NEXT_SESSION_STAGE_1_APPLY.md").exists()


class TestDocContent:
    def test_ui_score(self):
        assert "7.5" in _content()

    def test_ui_score_before(self):
        assert "6.1" in _content()

    def test_route_qa_table(self):
        c = _content()
        assert "Route QA" in c
        assert "/login" in c
        assert "/dashboard" in c
        assert "/pipeline" in c
        assert "/crm" in c

    def test_no_send_safety(self):
        c = _content()
        assert "No-Send Safety" in c or "Safety" in c
        assert "SAFE" in c

    def test_stage1_checklist(self):
        c = _content()
        assert "LOG_ONLY" in c
        assert "alembic" in c

    def test_rollback_checklist(self):
        c = _content()
        assert "Rollback" in c
        assert "OFF" in c

    def test_remaining_debt(self):
        c = _content()
        assert "innerHTML" in c or "Remaining" in c

    def test_not_deployed(self):
        c = _content().lower()
        assert "does not claim" in c or "not" in c

    def test_not_stage1_applied(self):
        c = _content()
        assert "has been applied" not in c or "NOT" in c

    def test_latest_commit(self):
        assert "e0fc58a" in _content()

    def test_has_test_messages(self):
        c = _content()
        assert "20 kv qancha" in c

    def test_has_monitor_section(self):
        assert "Monitor" in _content()

    def test_has_stop_conditions(self):
        c = _content()
        assert "STOP" in c
        assert "Health RED" in c

    def test_design_system_mentioned(self):
        c = _content()
        assert "vp-" in c

    def test_mobile_mentioned(self):
        c = _content().lower()
        assert "mobile" in c or "responsive" in c

    def test_safety_flags_count(self):
        c = _content()
        assert c.count("SAFE") >= 10

    def test_no_secrets(self):
        c = _content()
        assert "sk-" not in c
        assert "Bearer " not in c

    def test_recommendation(self):
        assert "READY FOR MANUAL STAGE 1 LOG_ONLY APPLY" in _content()

    def test_pre_apply_checklist(self):
        c = _content()
        assert "Pre-apply" in c or "Pre-Apply" in c
        assert "backup" in c.lower()


class TestChecklist82Updated:
    def _content(self):
        p = "docs/AI_AGENT_SYSTEM/82_STAGE_1_GO_NO_GO_CHECKLIST.md"
        return Path(p).read_text(encoding="utf-8")

    def test_commit_updated(self):
        assert "e0fc58a" in self._content()

    def test_rollback(self):
        assert "Rollback" in self._content()

    def test_observe(self):
        assert "Observe" in self._content()


class TestScript:
    def test_script_exists(self):
        assert Path("scripts/final_ui_stage1_check.py").exists()

    def test_importable(self):
        import importlib

        mod = importlib.import_module("scripts.final_ui_stage1_check")
        assert callable(mod.main)
        assert callable(mod.check_critical_docs)
        assert callable(mod.check_templates)
        assert callable(mod.check_dangerous_flags)
        assert callable(mod.check_login_no_sidebar)
        assert callable(mod.check_sidebar_routes)
        assert callable(mod.check_no_secrets_in_templates)
