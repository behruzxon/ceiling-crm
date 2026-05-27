"""Tests for Step AX — CRM UI templates."""
from __future__ import annotations

from pathlib import Path

_CONTACTS = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
_DETAIL = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
_BASE = Path("apps/web/templates/base.html").read_text(encoding="utf-8")

class TestSidebar:
    def test_crm_link(self):
        assert "/crm" in _BASE

class TestContactsPage:
    def test_search_input(self):
        assert "crmSearch" in _CONTACTS
    def test_status_filter(self):
        assert "crmStatusFilter" in _CONTACTS
    def test_temp_filter(self):
        assert "crmTempFilter" in _CONTACTS
    def test_contacts_table(self):
        assert "crmContactsTable" in _CONTACTS
    def test_empty_state(self):
        assert "crmEmptyState" in _CONTACTS
    def test_open_link(self):
        assert "Ochish" in _CONTACTS

class TestDetailPage:
    def test_chat_timeline(self):
        assert "chatTimeline" in _DETAIL
    def test_notes_section(self):
        assert "notesSection" in _DETAIL
    def test_tags_section(self):
        assert "tagsSection" in _DETAIL
    def test_operator_reply_section(self):
        assert "operatorReplySection" in _DETAIL
    def test_disabled_notice(self):
        assert "disabled" in _DETAIL.lower()
    def test_note_input(self):
        assert "noteInput" in _DETAIL
    def test_add_note_function(self):
        assert "addNote" in _DETAIL
    def test_no_script_injection(self):
        assert "<script>alert" not in _DETAIL

class TestWebRoutes:
    def test_crm_route(self):
        from apps.web.main import app
        paths = [r.path for r in app.routes]
        assert "/crm" in paths
    def test_detail_route(self):
        from apps.web.main import app
        paths = [r.path for r in app.routes]
        assert any("crm" in p and "contact_id" in p for p in paths)
