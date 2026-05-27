"""Tests for Step 3 — AI Trace Viewer in Contact Detail."""

from __future__ import annotations

from pathlib import Path


def _t() -> str:
    return Path(
        "apps/web/templates/crm_contact_detail.html",
    ).read_text(encoding="utf-8")


class TestTraceSection:
    def test_section_exists(self):
        assert "aiTraceSection" in _t()

    def test_title(self):
        assert "AI Trace Viewer" in _t()

    def test_subtitle(self):
        c = _t().lower()
        assert "ai" in c and "tushungan" in c


class TestBadges:
    def test_intent_badge(self):
        c = _t()
        assert "last_intent" in c and "vp-badge-info" in c

    def test_price_badge(self):
        c = _t()
        assert "last_price_estimate" in c and "vp-badge-success" in c

    def test_handoff_badge(self):
        c = _t()
        assert "handoff_requested" in c and "vp-badge-warning" in c

    def test_objection_badge(self):
        c = _t()
        assert "last_objection" in c and "vp-badge-hot" in c

    def test_safety_badge(self):
        c = _t()
        assert "safety_status" in c

    def test_log_only_badge(self):
        assert "LOG_ONLY" in _t()


class TestDetailFields:
    def test_area(self):
        assert "area_m2" in _t()

    def test_design(self):
        assert "design_type" in _t()

    def test_lead_score(self):
        assert "lead_score" in _t()


class TestEmptyState:
    def test_empty_message(self):
        c = _t()
        assert "AI trace yo'q" in c.lower() or "trace yo'q" in c.lower()

    def test_stage1_mention(self):
        c = _t()
        assert "Stage 1" in c or "LOG_ONLY" in c

    def test_vp_empty_state(self):
        assert "vp-empty-state" in _t()


class TestDesignSystem:
    def test_vp_card(self):
        assert "vp-card" in _t()

    def test_vp_badge(self):
        assert "vp-badge" in _t()


class TestNoSecrets:
    def test_no_token(self):
        assert "sk-" not in _t()

    def test_no_session_hash(self):
        assert "session_id_hash" not in _t()

    def test_no_openai_key(self):
        assert "OPENAI_API_KEY" not in _t()

    def test_no_db_url(self):
        assert "postgresql://" not in _t()

    def test_no_raw_json_dump(self):
        c = _t()
        assert "json.dumps" not in c.lower()


class TestMobile:
    def test_responsive(self):
        c = _t()
        assert "max-width" in c or "@media" in c


class TestDocExists:
    def test_doc_117(self):
        assert Path(
            "docs/AI_AGENT_SYSTEM/117_AI_TRACE_VIEWER_CONTACT_DETAIL.md",
        ).exists()


class TestSmoke:
    def test_web_imports(self):
        from apps.web.main import app

        assert app is not None

    def test_api_imports(self):
        from apps.api.main import app

        assert app is not None
