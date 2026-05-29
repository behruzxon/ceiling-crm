"""F6 — Admin Help page template + route tests."""

from __future__ import annotations

from pathlib import Path

_MAIN_PATH = Path("apps/web/main.py")
_HELP_PATH = Path("apps/web/templates/help.html")
_BASE_PATH = Path("apps/web/templates/base.html")

_MAIN = _MAIN_PATH.read_text(encoding="utf-8")
_HELP = _HELP_PATH.read_text(encoding="utf-8")
_BASE = _BASE_PATH.read_text(encoding="utf-8")


# ── Route presence ─────────────────────────────────────────────────────


class TestRoute:
    def test_route_defined(self) -> None:
        assert '@app.get("/help"' in _MAIN

    def test_route_calls_build_docs_index(self) -> None:
        assert "build_docs_index" in _MAIN

    def test_route_imports_build_docs_index(self) -> None:
        assert "from core.services.docs_index_service import build_docs_index" in _MAIN

    def test_route_renders_help_template(self) -> None:
        assert '"help.html"' in _MAIN

    def test_route_passes_docs_index_context(self) -> None:
        assert '"docs_index"' in _MAIN

    def test_docs_dir_constant_uses_repo_path(self) -> None:
        assert "_DOCS_DIR" in _MAIN
        assert "AI_AGENT_SYSTEM" in _MAIN


# ── Template exists / structure ───────────────────────────────────────


class TestTemplateStructure:
    def test_help_template_exists(self) -> None:
        assert _HELP_PATH.is_file()

    def test_extends_base(self) -> None:
        assert '{% extends "base.html" %}' in _HELP

    def test_active_page_help(self) -> None:
        assert "active_page" in _HELP
        assert '"help"' in _HELP

    def test_page_title_block(self) -> None:
        assert "Admin Help" in _HELP

    def test_summary_cards_present(self) -> None:
        assert "adminHelpSummaryCards" in _HELP

    def test_total_docs_card(self) -> None:
        assert "helpTotalDocs" in _HELP
        assert "idx.total_docs" in _HELP

    def test_group_count_card(self) -> None:
        assert "helpGroupCount" in _HELP

    def test_generated_at_card(self) -> None:
        assert "helpGeneratedAt" in _HELP
        assert "idx.generated_at" in _HELP

    def test_group_card_loop(self) -> None:
        assert "helpGroupCard" in _HELP
        assert "for g in idx.groups" in _HELP

    def test_group_description_renders(self) -> None:
        assert "helpGroupDescription" in _HELP
        assert "g.description" in _HELP

    def test_entry_loop_present(self) -> None:
        assert "for e in g.entries" in _HELP
        assert "helpDocItem" in _HELP

    def test_doc_title_renders(self) -> None:
        assert "helpDocTitle" in _HELP
        assert "e.title" in _HELP

    def test_doc_summary_renders(self) -> None:
        assert "helpDocSummary" in _HELP
        assert "e.summary" in _HELP

    def test_safe_badge_block(self) -> None:
        assert "helpDocSafeBadge" in _HELP

    def test_warning_badge_block(self) -> None:
        assert "helpDocWarningBadge" in _HELP

    def test_empty_state_block(self) -> None:
        assert "helpEmptyState" in _HELP


# ── Sidebar link ──────────────────────────────────────────────────────


class TestSidebar:
    def test_sidebar_has_help_link(self) -> None:
        assert "sidebarHelpLink" in _BASE

    def test_sidebar_link_target(self) -> None:
        assert 'href="/help"' in _BASE

    def test_sidebar_uses_active_page_help(self) -> None:
        assert "active_page == 'help'" in _BASE


# ── Styling ───────────────────────────────────────────────────────────


class TestStyling:
    def test_uses_vp_card(self) -> None:
        assert "vp-card" in _HELP

    def test_uses_vp_badge(self) -> None:
        assert "vp-badge" in _HELP


# ── No-send / no-POST guarantees ──────────────────────────────────────


class TestSafetyNoSendNoPOST:
    def test_no_send_button(self) -> None:
        for word in ("Yuborish", "Send live", "Send message", "Send Telegram"):
            assert word not in _HELP

    def test_no_save_button(self) -> None:
        for word in ("Saqlash", "Save change"):
            assert word not in _HELP

    def test_no_post_form(self) -> None:
        assert 'method="post"' not in _HELP.lower()
        assert "method='post'" not in _HELP.lower()
        assert "<form" not in _HELP.lower()

    def test_no_fetch_or_xhr(self) -> None:
        assert "fetch(" not in _HELP
        assert "XMLHttpRequest" not in _HELP

    def test_no_telegram_url(self) -> None:
        assert "t.me/" not in _HELP
        assert "api.telegram.org" not in _HELP
        assert "sendMessage" not in _HELP

    def test_no_openai_text_in_template(self) -> None:
        assert "openai.com" not in _HELP
        assert "api.openai.com" not in _HELP

    def test_no_flag_toggle_handlers(self) -> None:
        for h in ("previewSetting(", "previewPreset(", "applyPreset(", "rollbackSetting("):
            assert h not in _HELP


# ── No raw secrets in template ────────────────────────────────────────


class TestNoRawSecretsInTemplate:
    def test_no_raw_bot_token_string(self) -> None:
        # The literal string "BOT_TOKEN" must not appear in the
        # template — secret markers must come from redacted entries
        # at runtime.
        assert "BOT_TOKEN" not in _HELP

    def test_no_raw_openai_key_string(self) -> None:
        assert "OPENAI_API_KEY" not in _HELP

    def test_no_database_url_string(self) -> None:
        assert "DATABASE_URL" not in _HELP

    def test_no_sk_dash_literal(self) -> None:
        # "sk-" prefix would be a sign of a literal OpenAI key — none
        # should be hardcoded in the template.
        assert "sk-" not in _HELP

    def test_no_session_hash_text(self) -> None:
        assert "session_hash" not in _HELP

    def test_no_auth_bypass_text(self) -> None:
        for needle in ("bypass auth", "skip_auth", "disable_auth"):
            assert needle not in _HELP.lower()


# ── No auth bypass in route ───────────────────────────────────────────


class TestNoAuthBypass:
    def test_route_does_not_override_dependencies(self) -> None:
        # We accept any deps the app already injects; the new route
        # must not declare a `dependencies=[]` override that would
        # skip the dashboard-auth dependency.
        assert "dependencies=[]" not in _MAIN
