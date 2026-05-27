"""Tests for Step BV — Platform Readiness Audit Script."""

from __future__ import annotations

from scripts.platform_readiness_audit import (
    check_dangerous_flags,
    check_docs,
    check_imports,
    check_migrations,
)


class TestCheckImports:
    def test_all_ok(self):
        results = check_imports()
        assert len(results) >= 9
        for status, label, msg in results:
            assert status == "[OK]", f"{label} failed: {msg}"


class TestCheckDocs:
    def test_docs_present(self):
        results = check_docs()
        assert len(results) >= 7
        ok_count = sum(1 for r in results if r[0] == "[OK]")
        assert ok_count >= 7


class TestCheckDangerousFlags:
    def test_all_safe(self):
        results = check_dangerous_flags()
        assert len(results) >= 12
        for status, flag, msg in results:
            assert status != "[FAIL]", f"{flag}: {msg}"

    def test_defaults_false(self):
        results = check_dangerous_flags()
        for status, flag, msg in results:
            if "default=" in msg:
                assert "False" in msg or "not found" in msg, f"{flag} not safe: {msg}"


class TestCheckMigrations:
    def test_enough(self):
        results = check_migrations()
        assert results[0][0] == "[OK]"
        assert "42" in results[0][2] or int(results[0][2].split()[0]) >= 40


class TestNoSecretsPrinted:
    def test_imports_no_secrets(self):
        for _, _, msg in check_imports():
            assert "sk-" not in msg
            assert "token" not in msg.lower() or "Token" not in msg

    def test_flags_no_secrets(self):
        for _, _, msg in check_dangerous_flags():
            assert "sk-" not in msg
