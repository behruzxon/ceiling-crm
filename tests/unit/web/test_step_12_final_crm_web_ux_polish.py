"""Step 12 — Final CRM/Web UX polish tests.

Pure template assertions: sidebar links, empty states, badge consistency,
no fake ETA, no active send buttons, no token/phone/DB-URL leaks, mobile
responsive classes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3] / "apps" / "web" / "templates"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def base_src() -> str:
    return _read("base.html")


@pytest.fixture(scope="module")
def handoffs_src() -> str:
    return _read("crm_handoffs.html")


@pytest.fixture(scope="module")
def missed_src() -> str:
    return _read("crm_missed_leads.html")


@pytest.fixture(scope="module")
def analytics_src() -> str:
    return _read("analytics.html")


@pytest.fixture(scope="module")
def contact_src() -> str:
    return _read("crm_contact_detail.html")


# ----------------------------- base sidebar ---------------------------------


class TestBaseSidebar:
    def test_dashboard_link(self, base_src: str) -> None:
        assert 'href="/dashboard"' in base_src

    def test_pipeline_link(self, base_src: str) -> None:
        assert 'href="/pipeline"' in base_src

    def test_leads_link(self, base_src: str) -> None:
        assert 'href="/leads"' in base_src

    def test_crm_inbox_link(self, base_src: str) -> None:
        assert 'href="/crm"' in base_src

    def test_missed_leads_link(self, base_src: str) -> None:
        assert 'href="/crm/missed-leads"' in base_src

    def test_handoffs_link(self, base_src: str) -> None:
        assert 'href="/crm/handoffs"' in base_src

    def test_campaigns_link(self, base_src: str) -> None:
        assert 'href="/crm/campaigns"' in base_src

    def test_analytics_link(self, base_src: str) -> None:
        assert 'href="/analytics"' in base_src

    def test_agent_link(self, base_src: str) -> None:
        assert 'href="/agent"' in base_src

    def test_security_link(self, base_src: str) -> None:
        assert 'href="/admin/security"' in base_src

    def test_active_marker_used(self, base_src: str) -> None:
        assert "active_page" in base_src

    def test_sidebar_mobile_open_class(self, base_src: str) -> None:
        assert ".vp-sidebar.open" in base_src

    def test_topbar_titles_include_handoffs(self, base_src: str) -> None:
        assert "Handoff Queue" in base_src or "Handoffs" in base_src

    def test_topbar_titles_include_missed_leads(self, base_src: str) -> None:
        assert "Missed Leads" in base_src


# ----------------------------- handoffs page --------------------------------


class TestHandoffsPage:
    def test_has_digest_card(self, handoffs_src: str) -> None:
        assert "Daily Operator Digest" in handoffs_src

    def test_has_workload_card(self, handoffs_src: str) -> None:
        assert 'id="operatorWorkload"' in handoffs_src

    def test_has_assignment_filter(self, handoffs_src: str) -> None:
        assert 'id="assignedFilter"' in handoffs_src

    def test_has_expired_badge(self, handoffs_src: str) -> None:
        assert "expired-badge" in handoffs_src

    def test_has_expired_filter_option(self, handoffs_src: str) -> None:
        assert 'value="expired"' in handoffs_src

    def test_send_button_disabled(self, handoffs_src: str) -> None:
        # The digest send button must be present AND disabled
        import re

        assert re.search(r"<button[^>]*digest-send-btn[^>]*\bdisabled\b", handoffs_src) is not None

    def test_empty_state_friendly(self, handoffs_src: str) -> None:
        assert "Hozir navbatda handoff yo'q" in handoffs_src

    def test_link_to_standalone_digest(self, handoffs_src: str) -> None:
        assert 'href="/crm/operator-digest"' in handoffs_src

    def test_no_fake_eta(self, handoffs_src: str) -> None:
        for tok in ("ETA:", "ETA ", "min ichida"):
            assert tok not in handoffs_src

    def test_no_active_send_endpoint_in_digest(self, handoffs_src: str) -> None:
        assert "operator-digest/send" not in handoffs_src

    def test_take_button_preserved(self, handoffs_src: str) -> None:
        assert "'take'" in handoffs_src or "/take" in handoffs_src


# ----------------------------- missed leads ---------------------------------


class TestMissedLeadsPage:
    def test_kpi_critical(self, missed_src: str) -> None:
        assert "Critical" in missed_src

    def test_kpi_high(self, missed_src: str) -> None:
        assert "High" in missed_src

    def test_recommendations_card(self, missed_src: str) -> None:
        assert "Tavsiyalar" in missed_src

    def test_critical_badge_class(self, missed_src: str) -> None:
        assert "vp-badge-danger" in missed_src

    def test_high_badge_class(self, missed_src: str) -> None:
        assert "vp-badge-warning" in missed_src

    def test_low_badge_class(self, missed_src: str) -> None:
        assert "vp-badge-neutral" in missed_src

    def test_empty_state_friendly(self, missed_src: str) -> None:
        assert "Missed leadlar yo'q — hammasi nazoratda" in missed_src

    def test_mobile_media_query(self, missed_src: str) -> None:
        assert "max-width: 767px" in missed_src

    def test_filter_spacing(self, missed_src: str) -> None:
        assert "flex-wrap:wrap" in missed_src


# ------------------------------ analytics -----------------------------------


class TestAnalyticsPage:
    def test_charts_loading_state(self, analytics_src: str) -> None:
        assert 'id="chartsLoading"' in analytics_src
        assert "Charts yuklanmoqda" in analytics_src

    def test_charts_error_state(self, analytics_src: str) -> None:
        assert 'id="chartsError"' in analytics_src
        assert "yuklab bo'lmadi" in analytics_src.lower()

    def test_quick_links_to_missed(self, analytics_src: str) -> None:
        assert 'href="/crm/missed-leads"' in analytics_src

    def test_quick_links_to_handoffs(self, analytics_src: str) -> None:
        assert 'href="/crm/handoffs"' in analytics_src

    def test_chart_temperature_card(self, analytics_src: str) -> None:
        assert 'id="chartTemperature"' in analytics_src

    def test_chart_intent_card(self, analytics_src: str) -> None:
        assert 'id="chartIntent"' in analytics_src

    def test_chart_missed_card(self, analytics_src: str) -> None:
        assert 'id="chartMissed"' in analytics_src

    def test_chart_handoff_card(self, analytics_src: str) -> None:
        assert 'id="chartHandoff"' in analytics_src

    def test_empty_state_no_data(self, analytics_src: str) -> None:
        assert "No analytics data available" in analytics_src

    def test_mobile_grid_one_column(self, analytics_src: str) -> None:
        assert "grid-template-columns: 1fr" in analytics_src


# ----------------------------- contact detail -------------------------------


class TestContactDetailPage:
    def test_ai_trace_card(self, contact_src: str) -> None:
        assert "AI Trace Viewer" in contact_src

    def test_conversation_replay_card(self, contact_src: str) -> None:
        assert "Conversation Replay" in contact_src

    def test_price_history_card(self, contact_src: str) -> None:
        assert "Price Estimate History" in contact_src

    def test_ai_trace_empty_state(self, contact_src: str) -> None:
        assert "AI trace Stage 1 LOG_ONLY yoqilganda ko'rinadi" in contact_src

    def test_price_estimate_empty_state(self, contact_src: str) -> None:
        assert "Narx hisoblari hali yo'q" in contact_src

    def test_replay_empty_state(self, contact_src: str) -> None:
        assert "Replay uchun yetarli voqea yo'q" in contact_src

    def test_no_raw_json_dump(self, contact_src: str) -> None:
        # Should not blast metadata via |tojson dumps in template
        assert "| tojson" not in contact_src
        assert "|tojson" not in contact_src

    def test_log_only_badge_present(self, contact_src: str) -> None:
        assert "LOG_ONLY" in contact_src


# ----------------------------- no-leak guards -------------------------------


class TestNoLeaks:
    @pytest.fixture
    def all_src(
        self,
        base_src: str,
        handoffs_src: str,
        missed_src: str,
        analytics_src: str,
        contact_src: str,
    ) -> str:
        return "\n".join((base_src, handoffs_src, missed_src, analytics_src, contact_src))

    def test_no_bot_token_format(self, all_src: str) -> None:
        import re

        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", all_src)

    def test_no_session_hash(self, all_src: str) -> None:
        import re

        assert not re.search(r"\b[a-f0-9]{40,}\b", all_src)

    def test_no_openai_key(self, all_src: str) -> None:
        # No "OPENAI_API_KEY=" literal or "sk-" prefix anywhere
        assert "OPENAI_API_KEY=" not in all_src
        assert "sk-" not in all_src

    def test_no_db_password_url(self, all_src: str) -> None:
        assert "postgresql://" not in all_src
        assert "postgresql+asyncpg://" not in all_src
        assert "POSTGRES_PASSWORD=" not in all_src

    def test_no_bearer_literal(self, all_src: str) -> None:
        assert "Bearer " not in all_src


# ----------------------------- fake ETA guard -------------------------------


class TestNoFakeETA:
    @pytest.fixture
    def all_src(
        self,
        handoffs_src: str,
        missed_src: str,
        contact_src: str,
    ) -> str:
        return "\n".join((handoffs_src, missed_src, contact_src))

    def test_no_eta_token(self, all_src: str) -> None:
        for tok in ("ETA:", "ETA "):
            assert tok not in all_src

    def test_no_promise_words_in_handoffs(self, handoffs_src: str) -> None:
        # No outreach promise wording on the operator surface
        for tok in ("darhol yuboramiz", "bugun albatta yuboramiz"):
            assert tok not in handoffs_src

    def test_no_promise_words_in_missed(self, missed_src: str) -> None:
        for tok in ("darhol yuboramiz", "bugun albatta yuboramiz"):
            assert tok not in missed_src


# --------------------------- responsive presence ----------------------------


class TestMobileResponsive:
    def test_handoffs_has_mobile_media(self, handoffs_src: str) -> None:
        assert "max-width: 767px" in handoffs_src

    def test_missed_has_mobile_media(self, missed_src: str) -> None:
        assert "max-width: 767px" in missed_src

    def test_analytics_has_mobile_media(self, analytics_src: str) -> None:
        assert "max-width: 767px" in analytics_src

    def test_contact_has_mobile_grid(self, contact_src: str) -> None:
        assert "contact-grid" in contact_src

    def test_base_has_mobile_sidebar(self, base_src: str) -> None:
        assert "max-width: 1023px" in base_src
