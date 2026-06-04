"""Tests for the Knowledge Base web page + the Promote-to-FAQ UI.

Source-assertion + smoke style (matches the repo's web test convention).
"""

from __future__ import annotations

from pathlib import Path

_TPL = "apps/web/templates/agent_knowledge.html"
_UQ_TPL = "apps/web/templates/agent_unknown_questions.html"


def _t() -> str:
    return Path(_TPL).read_text(encoding="utf-8")


def _uq() -> str:
    return Path(_UQ_TPL).read_text(encoding="utf-8")


def _base() -> str:
    return Path("apps/web/templates/base.html").read_text(encoding="utf-8")


def _main() -> str:
    return Path("apps/web/main.py").read_text(encoding="utf-8")


class TestRouteExists:
    def test_web_route(self):
        assert "/agent/knowledge" in _main()

    def test_route_handler(self):
        assert "agent_knowledge" in _main()

    def test_template_exists(self):
        assert Path(_TPL).exists()

    def test_route_calls_summary_api(self):
        assert "/api/v1/admin/agent/knowledge/summary" in _main()

    def test_route_calls_list_api(self):
        assert "/api/v1/admin/agent/knowledge" in _main()


class TestSidebar:
    def test_sidebar_link(self):
        assert "/agent/knowledge" in _base()

    def test_active_highlight(self):
        assert "active_page == 'knowledge'" in _base()

    def test_topbar_title(self):
        assert "Bilimlar bazasi" in _base()


class TestActivePage:
    def test_active_page_set(self):
        assert 'active_page = "knowledge"' in _t()


class TestTitleAndNotice:
    def test_title(self):
        assert "Bilimlar bazasi" in _t()

    def test_subtitle(self):
        assert "FAQ" in _t() or "bilim" in _t().lower()

    def test_read_only_notice(self):
        # The page states bot lookup is default OFF and names the gating flag.
        c = _t()
        assert "AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED" in c
        assert "OFF" in c or "o'chiq" in c.lower()

    def test_no_toggle_button(self):
        # No live enable/disable control on the page (env-flag only).
        c = _t().lower()
        assert "toggle" not in c
        assert "enable_lookup" not in c

    def test_no_send_notice(self):
        assert "xabar yuborilmaydi" in _t()


class TestKPICards:
    def test_active_card(self):
        assert '"active"' in _t()

    def test_draft_card(self):
        assert '"draft"' in _t()

    def test_archived_card(self):
        assert '"archived"' in _t()

    def test_categories_card(self):
        assert "categories" in _t()

    def test_kpi_grid(self):
        assert "vp-kpi-grid" in _t()


class TestFilters:
    def test_status_filter(self):
        assert "statusFilter" in _t()

    def test_category_filter(self):
        assert "categoryFilter" in _t()

    def test_language_filter(self):
        assert "languageFilter" in _t()

    def test_search_filter(self):
        assert "qFilter" in _t()

    def test_apply_filters_js(self):
        assert "applyFilters" in _t()

    def test_refresh(self):
        assert "Yangilash" in _t()

    def test_all_categories_in_filter(self):
        t = _t()
        for cat in (
            "faq",
            "price",
            "catalog",
            "warranty",
            "objection",
            "service_area",
            "process",
            "other",
        ):
            assert f'value="{cat}"' in t, f"missing category option {cat}"


class TestTable:
    def test_vp_table(self):
        assert "vp-table" in _t()

    def test_shows_title(self):
        assert "item.title" in _t()

    def test_shows_question(self):
        assert "item.question" in _t()

    def test_shows_category(self):
        assert "item.category" in _t()

    def test_shows_status(self):
        assert "item.status" in _t()

    def test_shows_source(self):
        assert "item.source" in _t()

    def test_active_badge(self):
        assert "vp-badge-success" in _t()


class TestCreateEditModal:
    def test_modal_present(self):
        assert "kbModal" in _t()

    def test_create_button(self):
        assert "openCreate(" in _t()

    def test_edit_button(self):
        assert "openEdit(" in _t()

    def test_title_field(self):
        assert "kbTitle" in _t()

    def test_question_field(self):
        assert "kbQuestion" in _t()

    def test_answer_field(self):
        assert "kbAnswer" in _t()

    def test_category_field(self):
        assert "kbCategory" in _t()

    def test_status_field(self):
        assert "kbStatus" in _t()

    def test_aliases_field(self):
        assert "kbAliases" in _t()

    def test_tags_field(self):
        assert "kbTags" in _t()

    def test_submit_posts_to_api(self):
        assert "/api/v1/admin/agent/knowledge" in _t()

    def test_create_uses_post(self):
        assert "POST" in _t()

    def test_update_uses_patch(self):
        assert "PATCH" in _t()


class TestArchive:
    def test_archive_button(self):
        assert "archiveItem(" in _t()

    def test_archive_posts(self):
        assert "/archive" in _t()


class TestEmptyState:
    def test_empty_state(self):
        assert "vp-empty-state" in _t()

    def test_empty_message(self):
        assert "qo'shilmagan" in _t() or "FAQ ga o'tkazish" in _t()


class TestNoForbiddenActions:
    def test_no_send_button(self):
        assert "send_message" not in _t().lower()

    def test_no_auto_reply(self):
        assert "auto_reply" not in _t().lower()

    def test_no_token(self):
        assert "sk-" not in _t()


class TestPromoteOnUnknownQuestions:
    def test_promote_button_present(self):
        assert "openPromote(" in _uq()

    def test_promote_button_gated_to_new_reviewed(self):
        assert "('new', 'reviewed')" in _uq() or "'new', 'reviewed'" in _uq()

    def test_promote_modal_present(self):
        assert "promoteModal" in _uq()

    def test_promote_prefills_question(self):
        assert "promoteQuestion" in _uq()

    def test_promote_answer_field(self):
        assert "promoteAnswer" in _uq()

    def test_promote_category_field(self):
        assert "promoteCategory" in _uq()

    def test_promote_status_default_draft(self):
        s = _uq()
        assert "promoteStatus" in s and "draft" in s

    def test_promote_posts_to_api(self):
        assert "/promote-to-faq" in _uq()

    def test_promote_no_send_button(self):
        assert "send_message" not in _uq().lower()

    def test_promote_states_no_message_sent(self):
        assert "xabar yuborilmaydi" in _uq()


class TestSmoke:
    def test_web_app(self):
        from apps.web.main import app

        assert app is not None

    def test_template_parses(self):
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader("apps/web/templates"))
        assert env.get_template("agent_knowledge.html") is not None
        assert env.get_template("agent_unknown_questions.html") is not None
