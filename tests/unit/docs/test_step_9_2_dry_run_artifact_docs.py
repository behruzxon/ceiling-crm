"""Step 9.2 — Production dry-run JSON artifact docs tests.

Closes blocker §1.2 in
``docs/AI_AGENT_SYSTEM/134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md``.

These tests assert that the committed JSON artifact exists, is valid
JSON, contains no secrets, and that the accompanying doc 137 explains
the run with the correct safety guardrails.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_ARTIFACT = "docs/AI_AGENT_SYSTEM/_artifacts/production_deploy_dry_run_latest.json"
_DOC_137 = "docs/AI_AGENT_SYSTEM/137_PRODUCTION_DRY_RUN_JSON_ARTIFACT.md"
_DOC_134 = "docs/AI_AGENT_SYSTEM/134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md"
_SCRIPT = "scripts/production_deploy_dry_run_check.py"

_SECRET_PATTERNS = [
    r"BOT_TOKEN",
    r"OPENAI",
    r"DATABASE_URL",
    r"postgres://",
    r"Bearer ",
    r"sk-[A-Za-z0-9]{20,}",
]


def _text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _artifact_text() -> str:
    return _text(_ARTIFACT)


def _doc_text() -> str:
    return _text(_DOC_137)


class TestArtifact:
    def test_artifact_exists(self) -> None:
        assert Path(_ARTIFACT).is_file()

    def test_artifact_non_empty(self) -> None:
        assert len(_artifact_text()) > 100

    def test_artifact_valid_json(self) -> None:
        json.loads(_artifact_text())

    def test_artifact_has_overall(self) -> None:
        payload = json.loads(_artifact_text())
        assert payload.get("overall") in {"GREEN", "YELLOW", "RED"}

    def test_artifact_has_counts(self) -> None:
        payload = json.loads(_artifact_text())
        counts = payload.get("counts", {})
        for key in ("GREEN", "YELLOW", "RED"):
            assert key in counts
            assert isinstance(counts[key], int)

    def test_artifact_has_items_list(self) -> None:
        payload = json.loads(_artifact_text())
        assert isinstance(payload.get("items"), list)
        assert len(payload["items"]) > 10

    def test_artifact_items_have_required_keys(self) -> None:
        payload = json.loads(_artifact_text())
        for item in payload["items"]:
            assert {"status", "name", "detail"}.issubset(item.keys())

    def test_artifact_overall_not_red(self) -> None:
        payload = json.loads(_artifact_text())
        assert payload["overall"] != "RED"

    def test_artifact_zero_red_count(self) -> None:
        payload = json.loads(_artifact_text())
        assert payload["counts"]["RED"] == 0


class TestArtifactNoSecrets:
    def test_no_bot_token(self) -> None:
        assert "BOT_TOKEN" not in _artifact_text()

    def test_no_openai(self) -> None:
        assert "OPENAI" not in _artifact_text()

    def test_no_database_url(self) -> None:
        assert "DATABASE_URL" not in _artifact_text()

    def test_no_postgres_url(self) -> None:
        assert "postgres://" not in _artifact_text()

    def test_no_bearer_token(self) -> None:
        assert "Bearer " not in _artifact_text()

    def test_no_sk_token(self) -> None:
        assert re.search(r"sk-[A-Za-z0-9]{20,}", _artifact_text()) is None

    def test_no_secret_patterns_combined(self) -> None:
        text = _artifact_text()
        for pattern in _SECRET_PATTERNS:
            assert re.search(pattern, text) is None, f"secret pattern matched: {pattern}"


class TestDocExists:
    def test_doc_137_exists(self) -> None:
        assert Path(_DOC_137).is_file()

    def test_doc_137_non_empty(self) -> None:
        assert len(_doc_text()) > 800


class TestDocContent:
    def test_doc_references_command(self) -> None:
        assert "scripts/production_deploy_dry_run_check.py --json" in _doc_text()

    def test_doc_references_artifact_path(self) -> None:
        assert _ARTIFACT in _doc_text()

    def test_doc_says_no_deploy(self) -> None:
        assert "Deploy: NO" in _doc_text()

    def test_doc_says_no_vps(self) -> None:
        assert "VPS: NO" in _doc_text()

    def test_doc_says_no_flags(self) -> None:
        assert "Flags: NOT ENABLED" in _doc_text()

    def test_doc_says_stage_1_not_applied(self) -> None:
        assert "Stage 1 LOG_ONLY: NOT APPLIED" in _doc_text()

    def test_doc_says_no_production_migrations(self) -> None:
        assert "Production migrations: NOT RUN" in _doc_text()

    def test_doc_says_no_telegram_openai_calls(self) -> None:
        text = _doc_text()
        assert "Telegram" in text and "OpenAI" in text and "NOT CALLED" in text

    def test_doc_mentions_remaining_pg_dump_blocker(self) -> None:
        text = _doc_text()
        assert "pg_dump" in text
        assert "pg_restore" in text

    def test_doc_links_to_blocker_doc_134(self) -> None:
        assert "134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION" in _doc_text()

    def test_doc_records_result_summary(self) -> None:
        assert "Result summary" in _doc_text()

    def test_doc_records_date(self) -> None:
        assert "2026" in _doc_text()


class TestBlockerTrackerStillReferencesArtifactPath:
    def test_doc_134_mentions_artifacts_dir(self) -> None:
        # Sanity: doc 134 should still be the source-of-truth tracker
        # that points at the _artifacts/ directory.
        assert "_artifacts" in _text(_DOC_134)

    def test_script_supports_json_flag(self) -> None:
        # Sanity: the script we ran must still advertise --json.
        assert "--json" in _text(_SCRIPT)
