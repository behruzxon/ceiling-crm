"""F6 — Docs index service tests.

Verifies the read-only scanner: file selection, title / summary
extraction, group mapping, secret redaction, path-traversal defence,
and dataclass invariants. Uses pytest's tmp_path fixture so we never
touch the real docs tree.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.schemas.docs_index import (
    DocsIndex,
    DocsIndexEntry,
    DocsIndexGroup,
)
from core.services.docs_index_service import build_docs_index


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# ── Missing / empty dir ────────────────────────────────────────────────


class TestMissingAndEmpty:
    def test_none_dir_returns_empty_safely(self) -> None:
        result = build_docs_index(None)
        assert isinstance(result, DocsIndex)
        assert result.total_docs == 0
        assert "not provided" in result.empty_reason.lower()

    def test_missing_dir_returns_empty_safely(self, tmp_path: Path) -> None:
        result = build_docs_index(tmp_path / "does_not_exist")
        assert result.total_docs == 0
        assert "not found" in result.empty_reason.lower()

    def test_empty_dir_returns_empty_groups(self, tmp_path: Path) -> None:
        result = build_docs_index(tmp_path)
        assert result.total_docs == 0
        assert result.groups == ()
        assert "topilmadi" in result.empty_reason.lower()

    def test_string_path_accepted(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_x.md", "# Hello\n\nWorld.")
        result = build_docs_index(str(tmp_path))
        assert result.total_docs == 1


# ── File selection ─────────────────────────────────────────────────────


class TestFileSelection:
    def test_only_md_files_included(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# A\n\nbody")
        _write(tmp_path, "readme.txt", "ignore me")
        _write(tmp_path, "data.json", "{}")
        result = build_docs_index(tmp_path)
        names = {e.filename for g in result.groups for e in g.entries}
        assert names == {"100_a.md"}

    def test_dotfiles_skipped(self, tmp_path: Path) -> None:
        _write(tmp_path, ".secret.md", "# nope")
        _write(tmp_path, "100_a.md", "# A\n\nbody")
        result = build_docs_index(tmp_path)
        assert result.total_docs == 1
        names = {e.filename for g in result.groups for e in g.entries}
        assert ".secret.md" not in names

    def test_subdirectories_skipped(self, tmp_path: Path) -> None:
        nested = tmp_path / "nested"
        nested.mkdir()
        _write(nested, "150_inner.md", "# inner")
        _write(tmp_path, "100_top.md", "# top\n\nbody")
        result = build_docs_index(tmp_path)
        assert result.total_docs == 1
        names = {e.filename for g in result.groups for e in g.entries}
        assert "100_top.md" in names
        assert "150_inner.md" not in names

    def test_uppercase_md_extension_accepted(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.MD", "# A\n\nbody")
        result = build_docs_index(tmp_path)
        assert result.total_docs == 1


# ── Title extraction ──────────────────────────────────────────────────


class TestTitleExtraction:
    def test_title_from_first_h1(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title One\n\nbody")
        result = build_docs_index(tmp_path)
        entry = result.groups[0].entries[0]
        assert entry.title == "Title One"

    def test_title_fallback_to_filename(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_fallback.md", "no heading here\n\njust text")
        result = build_docs_index(tmp_path)
        entry = result.groups[0].entries[0]
        assert entry.title == "100_fallback"

    def test_blockquote_prologue_skipped_for_title(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "> Status: x\n\n# Real Title\n\nbody")
        result = build_docs_index(tmp_path)
        assert result.groups[0].entries[0].title == "Real Title"


# ── Summary extraction ────────────────────────────────────────────────


class TestSummaryExtraction:
    def test_summary_is_first_paragraph(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title\n\nThis is the summary.\n\nMore body.")
        result = build_docs_index(tmp_path)
        assert result.groups[0].entries[0].summary == "This is the summary."

    def test_summary_truncated_to_180(self, tmp_path: Path) -> None:
        long_para = "A" * 400
        _write(tmp_path, "100_a.md", f"# Title\n\n{long_para}")
        result = build_docs_index(tmp_path)
        assert len(result.groups[0].entries[0].summary) <= 181

    def test_summary_empty_when_only_headings(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title\n\n## Sub\n")
        result = build_docs_index(tmp_path)
        # No paragraph body — summary may be empty.
        assert result.groups[0].entries[0].summary == ""

    def test_summary_skips_blockquote_prologue(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "100_a.md",
            "# Title\n\n> Status: NO DEPLOY\n\nReal summary text.",
        )
        result = build_docs_index(tmp_path)
        assert "Real summary text" in result.groups[0].entries[0].summary

    def test_summary_joins_short_lines(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "100_a.md",
            "# Title\n\nLine one.\nLine two.\nLine three.\n\nBlock two.",
        )
        summary = build_docs_index(tmp_path).groups[0].entries[0].summary
        assert "Line one" in summary
        assert "Line two" in summary


# ── Numeric prefix sort ───────────────────────────────────────────────


class TestNumericSort:
    def test_sort_by_doc_id(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# A")
        _write(tmp_path, "050_b.md", "# B")
        _write(tmp_path, "200_c.md", "# C")
        result = build_docs_index(tmp_path)
        all_entries = [e for g in result.groups for e in g.entries]
        ids = [e.doc_id for e in all_entries]
        assert ids == sorted(ids)

    def test_no_number_gets_zero(self, tmp_path: Path) -> None:
        _write(tmp_path, "readme.md", "# Readme")
        result = build_docs_index(tmp_path)
        assert result.groups[0].entries[0].doc_id == 0


# ── Grouping ──────────────────────────────────────────────────────────


class TestGrouping:
    def test_foundation_range(self, tmp_path: Path) -> None:
        _write(tmp_path, "010_first.md", "# X")
        result = build_docs_index(tmp_path)
        areas = [g.area for g in result.groups]
        assert "foundation" in areas

    def test_stage1_prep_range(self, tmp_path: Path) -> None:
        _write(tmp_path, "075_x.md", "# X")
        areas = [g.area for g in build_docs_index(tmp_path).groups]
        assert "ai_agent_stage1_prep" in areas

    def test_crm_hardening_range(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_x.md", "# X")
        areas = [g.area for g in build_docs_index(tmp_path).groups]
        assert "crm_web_hardening" in areas

    def test_deployment_readiness_range(self, tmp_path: Path) -> None:
        _write(tmp_path, "125_x.md", "# X")
        areas = [g.area for g in build_docs_index(tmp_path).groups]
        assert "deployment_readiness" in areas

    def test_audit_local_polish_range(self, tmp_path: Path) -> None:
        _write(tmp_path, "135_x.md", "# X")
        areas = [g.area for g in build_docs_index(tmp_path).groups]
        assert "audit_local_polish" in areas

    def test_local_feature_docs_range(self, tmp_path: Path) -> None:
        _write(tmp_path, "141_x.md", "# X")
        areas = [g.area for g in build_docs_index(tmp_path).groups]
        assert "local_feature_docs" in areas

    def test_unknown_falls_into_other(self, tmp_path: Path) -> None:
        _write(tmp_path, "readme.md", "# Readme")
        areas = [g.area for g in build_docs_index(tmp_path).groups]
        assert "other" in areas

    def test_empty_groups_skipped(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_only.md", "# Only")
        result = build_docs_index(tmp_path)
        assert len(result.groups) == 1


# ── Metadata fields ───────────────────────────────────────────────────


class TestEntryMetadata:
    def test_total_docs_counted(self, tmp_path: Path) -> None:
        for i in (100, 110, 120):
            _write(tmp_path, f"{i}_x.md", f"# Doc {i}")
        result = build_docs_index(tmp_path)
        assert result.total_docs == 3

    def test_size_bytes_set(self, tmp_path: Path) -> None:
        body = "# A\n\nbody."
        path = _write(tmp_path, "100_a.md", body)
        result = build_docs_index(tmp_path)
        entry = result.groups[0].entries[0]
        assert entry.size_bytes == os.path.getsize(path)

    def test_generated_at_set(self, tmp_path: Path) -> None:
        result = build_docs_index(tmp_path)
        assert "UTC" in result.generated_at


# ── Secret redaction ──────────────────────────────────────────────────


class TestSecretRedaction:
    def test_bot_token_marker_redacted(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title\n\nMy BOT_TOKEN is exposed here.")
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "BOT_TOKEN" not in entry.summary
        assert entry.is_safe is False

    def test_openai_marker_redacted(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title\n\nOPENAI key inline.")
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "OPENAI" not in entry.summary
        assert entry.is_safe is False

    def test_database_url_marker_redacted(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title\n\nuse DATABASE_URL env.")
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "DATABASE_URL" not in entry.summary

    def test_postgres_url_redacted(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "100_a.md",
            "# Title\n\nuse postgres://user:pw@h:5432/db today.",
        )
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "postgres://user" not in entry.summary

    def test_redis_url_redacted(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "100_a.md",
            "# Title\n\nredis://default:pw@h:6379 is fine.",
        )
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "redis://default" not in entry.summary

    def test_bearer_redacted(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Title\n\nAuth Bearer abcd1234efgh.")
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "Bearer abcd1234" not in entry.summary

    def test_sk_token_redacted(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "100_a.md",
            "# Title\n\nKey is sk-abcdefghijklmnop1234 today.",
        )
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "sk-abcdefgh" not in entry.summary

    def test_telegram_bot_token_pattern_redacted(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            "100_a.md",
            "# Title\n\nMy token 1234567890:ABCDEFghijkLMNOPqrstUVWxyz123 fine.",
        )
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "ABCDEFghijkLMN" not in entry.summary

    def test_title_redaction_also_flags_unsafe(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# OPENAI in title\n\nclean body.")
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert "OPENAI" not in entry.title
        assert entry.is_safe is False
        assert "redacted" in entry.warning.lower()

    def test_clean_doc_is_safe(self, tmp_path: Path) -> None:
        _write(tmp_path, "100_a.md", "# Clean Title\n\nNothing scary here.")
        entry = build_docs_index(tmp_path).groups[0].entries[0]
        assert entry.is_safe is True
        assert entry.warning == ""


# ── Path-traversal defence ─────────────────────────────────────────────


class TestPathTraversal:
    def test_outside_directory_not_iterated(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("# Outside\n\nshould not appear")
        inside_dir = tmp_path / "docs"
        inside_dir.mkdir()
        _write(inside_dir, "100_inside.md", "# Inside\n\nshould appear")
        result = build_docs_index(inside_dir)
        names = {e.filename for g in result.groups for e in g.entries}
        assert names == {"100_inside.md"}

    @pytest.mark.skipif(
        not hasattr(os, "symlink") or os.name == "nt",
        reason="symlink test requires POSIX and elevated rights on Windows",
    )
    def test_symlink_outside_dropped(self, tmp_path: Path) -> None:
        outside = tmp_path / "outside.md"
        outside.write_text("# Outside\n\nshould not appear")
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        _write(docs_dir, "100_inside.md", "# Inside\n\nbody")
        link = docs_dir / "999_link.md"
        os.symlink(outside, link)
        result = build_docs_index(docs_dir)
        names = {e.filename for g in result.groups for e in g.entries}
        assert "999_link.md" not in names


# ── Frozen dataclass ──────────────────────────────────────────────────


class TestFrozen:
    def test_index_is_frozen(self) -> None:
        idx = DocsIndex()
        try:
            idx.total_docs = 99  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("DocsIndex should be frozen")

    def test_group_is_frozen(self) -> None:
        g = DocsIndexGroup()
        try:
            g.area = "x"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("DocsIndexGroup should be frozen")

    def test_entry_is_frozen(self) -> None:
        e = DocsIndexEntry()
        try:
            e.title = "x"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("DocsIndexEntry should be frozen")


# ── Real repo smoke ───────────────────────────────────────────────────


class TestRealRepoSmoke:
    def test_real_docs_dir_returns_groups(self) -> None:
        repo_docs = Path("docs") / "AI_AGENT_SYSTEM"
        if not repo_docs.is_dir():
            pytest.skip("docs/AI_AGENT_SYSTEM not present")
        result = build_docs_index(repo_docs)
        assert result.total_docs > 0
        assert len(result.groups) >= 1
