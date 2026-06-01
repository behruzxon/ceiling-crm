"""Tests for the Unknown Questions Inbox web page (read-only triage UI).

Source-assertion + smoke style (matches the repo's web test convention):
verify the route, template, nav, KPI cards, filters, table, review form,
empty state, and the absence of any send / convert-to-FAQ / secret surface.
"""

from __future__ import annotations

from pathlib import Path

_TPL = "apps/web/templates/agent_unknown_questions.html"


def _t() -> str:
    return Path(_TPL).read_text(encoding="utf-8")


def _base() -> str:
    return Path("apps/web/templates/base.html").read_text(encoding="utf-8")


def _main() -> str:
    return Path("apps/web/main.py").read_text(encoding="utf-8")


class TestRouteExists:
    def test_web_route(self) -> None:
        assert "/agent/unknown-questions" in _main()

    def test_route_handler(self) -> None:
        assert "agent_unknown_questions" in _main()

    def test_template_exists(self) -> None:
        assert Path(_TPL).exists()

    def test_route_calls_summary_api(self) -> None:
        assert "/api/v1/admin/agent/unknown-questions/summary" in _main()

    def test_route_calls_list_api(self) -> None:
        assert "/api/v1/admin/agent/unknown-questions" in _main()


class TestSidebar:
    def test_sidebar_link(self) -> None:
        assert "/agent/unknown-questions" in _base()

    def test_active_highlight(self) -> None:
        assert "active_page == 'unknown_questions'" in _base()

    def test_topbar_title(self) -> None:
        assert "Unknown Questions" in _base()


class TestActivePage:
    def test_active_page_set(self) -> None:
        assert 'active_page = "unknown_questions"' in _t()


class TestTitle:
    def test_title(self) -> None:
        assert "Unknown Questions" in _t()

    def test_subtitle(self) -> None:
        assert "savol" in _t().lower()


class TestReadOnlyNotice:
    def test_read_only_banner(self) -> None:
        assert "read-only" in _t().lower()

    def test_states_no_send(self) -> None:
        assert "xabar yubormaydi" in _t()


class TestKPICards:
    def test_new_card(self) -> None:
        assert "total_new" in _t()

    def test_high_severity_card(self) -> None:
        assert "high_severity" in _t()

    def test_today_card(self) -> None:
        assert "today_count" in _t()

    def test_top_reason_card(self) -> None:
        assert "top_reason" in _t()

    def test_kpi_grid(self) -> None:
        assert "vp-kpi-grid" in _t()


class TestFilters:
    def test_status_filter(self) -> None:
        assert "statusFilter" in _t()

    def test_reason_filter(self) -> None:
        assert "reasonFilter" in _t()

    def test_severity_filter(self) -> None:
        assert "severityFilter" in _t()

    def test_search_filter(self) -> None:
        assert "qFilter" in _t()

    def test_refresh(self) -> None:
        assert "Yangilash" in _t()

    def test_apply_filters_js(self) -> None:
        assert "applyFilters" in _t()


class TestTable:
    def test_vp_table(self) -> None:
        assert "vp-table" in _t()

    def test_shows_preview(self) -> None:
        assert "original_text_preview" in _t()

    def test_shows_reason(self) -> None:
        assert "item.reason" in _t()

    def test_shows_severity_badge(self) -> None:
        assert "vp-badge-danger" in _t()

    def test_shows_status(self) -> None:
        assert "item.status" in _t()

    def test_shows_created_at(self) -> None:
        assert "created_at" in _t()

    def test_shows_intent_route_sdm(self) -> None:
        s = _t()
        assert "item.intent" in s and "item.live_route" in s and "item.sdm_next_action" in s

    def test_contact_link_when_available(self) -> None:
        assert "/crm/{{ item.crm_contact_id }}" in _t()


class TestReviewForm:
    def test_review_modal(self) -> None:
        assert "reviewModal" in _t()

    def test_review_status_select(self) -> None:
        assert "reviewStatus" in _t()

    def test_review_note(self) -> None:
        assert "reviewNote" in _t()

    def test_review_posts_to_api(self) -> None:
        assert "/api/v1/admin/agent/unknown-questions/" in _t()
        assert "review" in _t()

    def test_review_status_options(self) -> None:
        s = _t()
        assert "reviewed" in s and "needs_operator" in s and "ignored" in s

    def test_mark_reviewed(self) -> None:
        assert "Ko'rib chiqilgan" in _t()


class TestEmptyState:
    def test_empty_state(self) -> None:
        assert "vp-empty-state" in _t()

    def test_empty_message(self) -> None:
        assert "yo'q" in _t().lower()


class TestNoForbiddenActionsYet:
    def test_no_send_message_button(self) -> None:
        c = _t().lower()
        assert "send_message" not in c

    def test_no_auto_reply_action(self) -> None:
        assert "auto_reply" not in _t().lower()

    def test_promote_to_faq_present(self) -> None:
        # As of the Knowledge Base CRUD sprint, Promote-to-FAQ IS present here.
        # It creates a knowledge item via the API; it does NOT send or auto-reply.
        s = _t()
        assert "/promote-to-faq" in s
        assert "openPromote(" in s

    def test_promote_states_no_message_sent(self) -> None:
        assert "xabar yuborilmaydi" in _t()


class TestMobile:
    def test_responsive(self) -> None:
        assert "@media" in _t() or "max-width" in _t()


class TestSafety:
    def test_no_token(self) -> None:
        assert "sk-" not in _t()

    def test_no_chat_id_hash_exposed(self) -> None:
        assert "telegram_chat_id_hash" not in _t()

    def test_no_phone_field_rendered(self) -> None:
        # The page must not render a raw phone column.
        assert "item.phone" not in _t()


class TestSmoke:
    def test_web_app(self) -> None:
        from apps.web.main import app

        assert app is not None

    def test_template_parses(self) -> None:
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader("apps/web/templates"))
        assert env.get_template("agent_unknown_questions.html") is not None


# ── v2: expanded reason coverage in the filter UI ─────────────────────────────


class TestV2ReasonFilters:
    def test_unknown_price_question_option_present(self) -> None:
        assert 'value="unknown_price_question"' in _t()

    def test_no_catalog_match_option_present(self) -> None:
        assert 'value="no_catalog_match"' in _t()

    def test_unknown_design_option_present(self) -> None:
        assert 'value="unknown_design"' in _t()

    def test_all_v2_reasons_selectable(self) -> None:
        t = _t()
        for reason in (
            "ai_fallback",
            "openai_error",
            "safety_block",
            "no_catalog_match",
            "unknown_price_question",
            "unknown_design",
            "low_confidence",
            "shadow_live_mismatch",
        ):
            assert f'value="{reason}"' in t, f"missing filter option: {reason}"

    def test_summary_top_reasons_still_rendered(self) -> None:
        # top_reasons is dynamic (DB group-by), so new reasons render automatically.
        assert "top_reasons" in _t()

    def test_still_no_send_or_faq_buttons(self) -> None:
        s = _t()
        assert "send_message" not in s.lower()
        assert "create_faq" not in s
