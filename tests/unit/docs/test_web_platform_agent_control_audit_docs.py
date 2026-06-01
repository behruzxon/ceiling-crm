"""Docs test for doc 152 — Web Platform Agent Control Audit.

This is a docs-only audit deliverable. The tests assert the document exists and
contains every required section: the 12 scored areas, the top-30 missing-feature
list, the recommended next sprint, the no-production-deploy contract, and the
post-deploy knowledge/pricing/catalog upgrade requirements.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOC = "docs/AI_AGENT_SYSTEM/152_WEB_PLATFORM_AGENT_CONTROL_AUDIT.md"

# The 12 score areas, exactly as enumerated in the audit request.
_SCORE_AREAS = (
    "Agent Control Center",
    "CRM Contact Detail",
    "Knowledge Management",
    "Price Management",
    "Catalog Management",
    "Failed Question Intelligence",
    "Shadow / SDM Monitoring",
    "Operator Workflow",
    "Feature Flags / Safe Enablement",
    "Analytics / KPIs",
    "Security / Privacy",
    "Post-deploy Upgrade Ability",
)


def _c() -> str:
    return Path(_DOC).read_text(encoding="utf-8")


class TestDocExists:
    def test_doc_exists(self) -> None:
        assert Path(_DOC).exists()

    def test_doc_non_trivial(self) -> None:
        assert len(_c()) > 8000


class TestScoreAreas:
    def test_all_twelve_score_areas_present(self) -> None:
        text = _c()
        for area in _SCORE_AREAS:
            assert area in text, f"missing score area: {area}"

    def test_scoring_table_uses_out_of_ten(self) -> None:
        assert "/10" in _c()

    def test_each_area_has_a_score(self) -> None:
        # Scores are written like **8/10**, **1/10**, etc. Expect at least 12.
        found = re.findall(r"\*\*\d{1,2}/10\*\*", _c())
        assert len(found) >= 12, f"only {len(found)} per-area scores found"

    def test_overall_score_present(self) -> None:
        assert re.search(r"[Oo]verall.*\d", _c()) is not None


class TestVerdict:
    def test_verdict_section_present(self) -> None:
        assert "Verdict" in _c()

    def test_partial_verdict_present(self) -> None:
        assert "PARTIAL" in _c()

    def test_biggest_missing_piece_present(self) -> None:
        assert "iggest missing piece" in _c()


class TestTop30MissingFeatures:
    def test_top_30_heading_present(self) -> None:
        assert "Top 30 missing features" in _c()

    def test_thirty_numbered_features(self) -> None:
        # Items are written as "### 1." through "### 30.".
        found = re.findall(r"^###\s+\d+\.", _c(), re.MULTILINE)
        assert len(found) >= 30, f"only {len(found)} numbered features found"

    def test_priorities_present(self) -> None:
        text = _c()
        for p in ("P0", "P1", "P2", "P3"):
            assert p in text, f"missing priority tier {p}"

    def test_features_state_risk(self) -> None:
        assert "Risk:" in _c()

    def test_features_state_files(self) -> None:
        assert "Files:" in _c()


class TestUpgradeRoadmap:
    def test_upgrade_system_roadmap_present(self) -> None:
        assert "Agent upgrade system" in _c() or "upgrade system" in _c()

    def test_roadmap_mentions_key_pieces(self) -> None:
        text = _c()
        for piece in (
            "Unknown Questions Inbox",
            "Knowledge Base CRUD",
            "Shadow Decision Viewer",
            "Parity Dashboard",
            "Versioning",
            "Rollback",
            "Approval",
            "Training Queue",
            "Alias",
        ):
            assert piece in text, f"roadmap missing: {piece}"


class TestRecommendedNextSprint:
    def test_recommended_next_sprint_present(self) -> None:
        assert "Recommended next sprint" in _c() or "Recommended Next Sprint" in _c()

    def test_exactly_one_sprint_chosen(self) -> None:
        # The audit must commit to Unknown Questions Inbox as the single sprint.
        assert "Unknown Questions Inbox" in _c()


class TestCannotLearnSection:
    def test_what_agent_cannot_learn_present(self) -> None:
        text = _c()
        assert "cannot learn from the web" in text or "still cannot learn" in text


class TestNoProductionDeployContract:
    def test_no_deploy(self) -> None:
        assert "Deploy: NO" in _c()

    def test_no_vps(self) -> None:
        assert "VPS: NO" in _c()

    def test_flags_not_enabled(self) -> None:
        assert "Flags: NOT ENABLED" in _c()

    def test_live_sender_not_enabled(self) -> None:
        assert "Live sender: NOT ENABLED" in _c()

    def test_audit_only_statement(self) -> None:
        assert "AUDIT-ONLY" in _c() or "AUDIT ONLY" in _c()

    def test_db_not_modified(self) -> None:
        text = _c()
        assert "NOT MODIFIED" in text or "NOT modified" in text


class TestPostDeployUpgradeRequirements:
    def test_post_deploy_section_present(self) -> None:
        assert "Post-deploy" in _c() or "post-deploy" in _c()

    def test_mentions_knowledge_upgrade(self) -> None:
        text = _c()
        assert "Knowledge" in text and ("hardcoded" in text or "deploy + bot restart" in text)

    def test_mentions_pricing_upgrade(self) -> None:
        assert "Price" in _c() and "pricing.py" in _c()

    def test_mentions_catalog_upgrade(self) -> None:
        assert "Catalog" in _c() and "catalog.py" in _c()

    def test_mentions_restart_requirement(self) -> None:
        assert "restart" in _c().lower()


class TestNoSecretLeaks:
    def test_no_bot_token_format(self) -> None:
        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", _c())

    def test_no_real_openai_key(self) -> None:
        assert not re.search(r"sk-[A-Za-z0-9]{20,}", _c())

    def test_no_db_url_with_credentials(self) -> None:
        assert not re.search(r"postgresql(?:\+asyncpg)?://[^@\s]+:[^@\s]+@", _c())
