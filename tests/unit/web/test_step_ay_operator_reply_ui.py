"""Tests for Step AY — Operator Reply UI."""
from __future__ import annotations

from pathlib import Path

_DETAIL = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")

class TestReplySection:
    def test_section_exists(self):
        assert "operatorReplySection" in _DETAIL
    def test_disabled_notice(self):
        assert "replyDisabledNotice" in _DETAIL
    def test_textarea(self):
        assert "replyTextarea" in _DETAIL
    def test_preview_button(self):
        assert "previewBtn" in _DETAIL
    def test_send_button(self):
        assert "sendBtn" in _DETAIL
    def test_confirm_warning(self):
        assert "replyConfirmWarn" in _DETAIL
    def test_blockers_panel(self):
        assert "replyBlockers" in _DETAIL
    def test_warnings_panel(self):
        assert "replyWarnings" in _DETAIL
    def test_result_panel(self):
        assert "replyResult" in _DETAIL
    def test_audit_section(self):
        assert "replyAuditSection" in _DETAIL
    def test_js_preview(self):
        assert "previewReply" in _DETAIL
    def test_js_send(self):
        assert "sendReply" in _DETAIL
    def test_uzbek_text(self):
        assert "Javob yozish" in _DETAIL
    def test_confirm_text(self):
        assert "real mijozga yuboriladi" in _DETAIL
    def test_no_secret(self):
        assert "bot_token" not in _DETAIL.lower()
        assert "api_key" not in _DETAIL.lower()
