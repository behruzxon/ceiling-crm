"""Full-codebase AI + web platform audit docs tests (docs 131–135).

Note on numbering: the user's audit request asked for docs at 125–129. Those slots
were already filled by recent implementation docs (Stage 1 readiness, operator digest,
UX polish, production deployment runbook, dry-run check). To avoid overwriting them,
the audit pack lives at 131–135. This test file validates that pack.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOC_125 = "docs/AI_AGENT_SYSTEM/131_FULL_CODEBASE_AI_WEB_PLATFORM_AUDIT.md"
_DOC_126 = "docs/AI_AGENT_SYSTEM/132_AI_AGENT_PLATFORM_CAPABILITY_MAP.md"
_DOC_127 = "docs/AI_AGENT_SYSTEM/133_NEXT_50_IMPROVEMENTS_ROADMAP.md"
_DOC_128 = "docs/AI_AGENT_SYSTEM/134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md"
_DOC_129 = "docs/AI_AGENT_SYSTEM/135_TEST_AND_CI_HARDENING_AUDIT.md"


def _c(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _all() -> str:
    return "\n".join(_c(p) for p in (_DOC_125, _DOC_126, _DOC_127, _DOC_128, _DOC_129))


# ─────────────────────────────────────────────────────────────────────────────
# Existence + minimum size
# ─────────────────────────────────────────────────────────────────────────────


class TestDocsExist:
    def test_doc_125_full_codebase_audit_exists(self) -> None:
        assert Path(_DOC_125).exists()

    def test_doc_126_capability_map_exists(self) -> None:
        assert Path(_DOC_126).exists()

    def test_doc_127_roadmap_exists(self) -> None:
        assert Path(_DOC_127).exists()

    def test_doc_128_blockers_exists(self) -> None:
        assert Path(_DOC_128).exists()

    def test_doc_129_test_audit_exists(self) -> None:
        assert Path(_DOC_129).exists()

    def test_doc_125_non_trivial(self) -> None:
        assert len(_c(_DOC_125)) > 4000

    def test_doc_126_non_trivial(self) -> None:
        assert len(_c(_DOC_126)) > 4000

    def test_doc_127_non_trivial(self) -> None:
        assert len(_c(_DOC_127)) > 3500

    def test_doc_128_non_trivial(self) -> None:
        assert len(_c(_DOC_128)) > 2500

    def test_doc_129_non_trivial(self) -> None:
        assert len(_c(_DOC_129)) > 2500


# ─────────────────────────────────────────────────────────────────────────────
# Doc 125 — Full codebase audit content
# ─────────────────────────────────────────────────────────────────────────────


class TestDoc125FullCodebaseAudit:
    def test_architecture_section(self) -> None:
        assert "Architecture" in _c(_DOC_125)

    def test_bot_section(self) -> None:
        assert "Telegram Bot" in _c(_DOC_125) or "Bot Audit" in _c(_DOC_125)

    def test_ai_section(self) -> None:
        assert "AI Agent" in _c(_DOC_125) or "Agent Capability" in _c(_DOC_125)

    def test_web_section(self) -> None:
        assert "Web CRM" in _c(_DOC_125)

    def test_security_section(self) -> None:
        assert "Security" in _c(_DOC_125)

    def test_performance_section(self) -> None:
        assert "Performance" in _c(_DOC_125) or "Scale" in _c(_DOC_125)

    def test_business_value_section(self) -> None:
        assert "Business" in _c(_DOC_125)

    def test_scorecard_present(self) -> None:
        text = _c(_DOC_125)
        assert "/10" in text or "out of 10" in text.lower()

    def test_overall_score_present(self) -> None:
        text = _c(_DOC_125)
        assert re.search(r"Overall.*\d\.\d", text, re.IGNORECASE) is not None

    def test_database_section(self) -> None:
        assert "Database" in _c(_DOC_125) or "Migrations" in _c(_DOC_125)

    def test_scheduler_section(self) -> None:
        assert "Scheduler" in _c(_DOC_125)


# ─────────────────────────────────────────────────────────────────────────────
# Doc 126 — Capability map content
# ─────────────────────────────────────────────────────────────────────────────


class TestDoc126CapabilityMap:
    def test_agent_can_see_section(self) -> None:
        assert "What the agent can see" in _c(_DOC_126)

    def test_agent_can_decide_section(self) -> None:
        assert "What the agent can decide" in _c(_DOC_126)

    def test_agent_can_do_section(self) -> None:
        assert "What the agent can do" in _c(_DOC_126)

    def test_agent_cannot_do_section(self) -> None:
        assert "What the agent cannot do" in _c(_DOC_126)

    def test_blind_spots_section(self) -> None:
        assert "Blind spots" in _c(_DOC_126) or "blind spot" in _c(_DOC_126).lower()

    def test_levels_0_through_5_present(self) -> None:
        text = _c(_DOC_126)
        for n in range(0, 6):
            assert f"Level {n}" in text, f"missing Level {n}"

    def test_level_0_describes_log_only(self) -> None:
        text = _c(_DOC_126)
        assert "LOG_ONLY" in text

    def test_level_5_marked_not_ready(self) -> None:
        text = _c(_DOC_126)
        assert "NOT READY" in text

    def test_safety_gates_mentioned(self) -> None:
        text = _c(_DOC_126)
        assert "sandbox" in text.lower() and "approval" in text.lower()

    def test_capability_score_present(self) -> None:
        text = _c(_DOC_126)
        assert "score" in text.lower() and "/10" in text


# ─────────────────────────────────────────────────────────────────────────────
# Doc 127 — Roadmap content
# ─────────────────────────────────────────────────────────────────────────────


class TestDoc127Roadmap:
    def test_50_improvements_present(self) -> None:
        text = _c(_DOC_127)
        # Numbered items: at least 50 of "### 1." through "### 50."
        found = re.findall(r"^###\s+\d+\.", text, re.MULTILINE)
        assert len(found) >= 50, f"only {len(found)} numbered items found"

    def test_phases_present(self) -> None:
        text = _c(_DOC_127)
        for phase in range(0, 11):
            assert f"Phase {phase}" in text, f"missing Phase {phase}"

    def test_phase_0_before_stage_1(self) -> None:
        text = _c(_DOC_127)
        assert "Phase 0" in text and "Stage 1" in text

    def test_impact_dimension(self) -> None:
        text = _c(_DOC_127)
        assert "Impact" in text or "impact" in text

    def test_risk_dimension(self) -> None:
        text = _c(_DOC_127)
        assert "Risk" in text or "risk" in text

    def test_complexity_dimension(self) -> None:
        text = _c(_DOC_127)
        assert "Complexity" in text or "complexity" in text


# ─────────────────────────────────────────────────────────────────────────────
# Doc 128 — Blockers and Stage 1 decision content
# ─────────────────────────────────────────────────────────────────────────────


class TestDoc128Blockers:
    def test_blockers_section(self) -> None:
        assert "Blockers" in _c(_DOC_128) or "blocker" in _c(_DOC_128).lower()

    def test_stage_1_section(self) -> None:
        assert "Stage 1" in _c(_DOC_128)

    def test_conditional_go_verdict(self) -> None:
        text = _c(_DOC_128)
        assert "CONDITIONAL GO" in text or "CONDITIONAL" in text

    def test_rollback_section(self) -> None:
        assert "Rollback" in _c(_DOC_128) or "rollback" in _c(_DOC_128).lower()

    def test_security_requirements_section(self) -> None:
        text = _c(_DOC_128)
        assert "security" in text.lower() and (
            "checklist" in text.lower() or "required" in text.lower()
        )

    def test_final_recommendation_present(self) -> None:
        assert "recommendation" in _c(_DOC_128).lower()

    def test_pg_dump_drill_mentioned(self) -> None:
        assert "pg_dump" in _c(_DOC_128)

    def test_dry_run_check_mentioned(self) -> None:
        assert "production_deploy_dry_run_check" in _c(_DOC_128)


# ─────────────────────────────────────────────────────────────────────────────
# Doc 129 — Test + CI hardening content
# ─────────────────────────────────────────────────────────────────────────────


class TestDoc129TestAudit:
    def test_test_quality_section(self) -> None:
        text = _c(_DOC_129)
        assert "Test quality" in text or "test quality" in text.lower()

    def test_ci_section(self) -> None:
        text = _c(_DOC_129)
        assert "CI" in text

    def test_mypy_debt_section(self) -> None:
        text = _c(_DOC_129)
        assert "mypy" in text.lower() and ("debt" in text.lower() or "non-blocking" in text.lower())

    def test_missing_tests_listed(self) -> None:
        text = _c(_DOC_129)
        # At least 40 missing tests should be enumerated as a numbered list.
        found = re.findall(r"^\d+\.\s+", text, re.MULTILINE)
        assert len(found) >= 40

    def test_simulation_lab_mentioned(self) -> None:
        text = _c(_DOC_129)
        assert "simulation" in text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Cross-doc status contract — must not claim deployed or Stage 1 applied
# ─────────────────────────────────────────────────────────────────────────────


class TestStatusContract:
    def test_docs_do_not_claim_deployed(self) -> None:
        text = _all()
        # The audit must explicitly say Deploy: NO at the top of each doc.
        assert text.count("Deploy: NO") >= 5

    def test_docs_do_not_claim_vps_up(self) -> None:
        text = _all()
        assert text.count("VPS: NO") >= 5

    def test_docs_do_not_claim_stage1_applied(self) -> None:
        text = _all()
        # "NOT APPLIED" appears at the top of every doc.
        assert text.count("NOT APPLIED") >= 5

    def test_docs_say_flags_not_enabled(self) -> None:
        text = _all()
        assert text.count("Flags: NOT ENABLED") >= 5

    def test_docs_say_live_sender_not_enabled(self) -> None:
        text = _all()
        assert "Live sender: NOT ENABLED" in text

    def test_docs_say_campaign_send_not_enabled(self) -> None:
        text = _all()
        assert "Campaign send: NOT ENABLED" in text

    def test_docs_say_operator_reply_not_enabled(self) -> None:
        text = _all()
        assert "Operator reply live send: NOT ENABLED" in text


# ─────────────────────────────────────────────────────────────────────────────
# Secret-leak guard — no real-looking tokens, keys, or DB URLs
# ─────────────────────────────────────────────────────────────────────────────


class TestNoSecretLeaks:
    def test_no_bot_token_format(self) -> None:
        # Telegram bot tokens look like: <8-12 digits>:<35+ alphanumeric>
        # The docs reference the env var name but never a real value.
        text = _all()
        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", text)

    def test_no_real_openai_key(self) -> None:
        text = _all()
        # Real keys are at least 20 chars after "sk-".
        assert not re.search(r"sk-[A-Za-z0-9]{20,}", text)
        assert not re.search(r"OPENAI_API_KEY=[A-Za-z0-9_-]{20,}", text)

    def test_no_db_url_with_credentials(self) -> None:
        text = _all()
        assert not re.search(r"postgresql(?:\+asyncpg)?://[^@\s]+:[^@\s]+@", text)

    def test_no_aws_access_key_literal(self) -> None:
        text = _all()
        assert not re.search(r"AKIA[0-9A-Z]{16}", text)

    def test_no_bearer_token_literal(self) -> None:
        text = _all()
        # Allow "Bearer token" as a phrase; forbid actual base64-looking tokens after Bearer.
        assert not re.search(r"Bearer\s+[A-Za-z0-9_\-\.=]{20,}", text)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-doc references should be navigable
# ─────────────────────────────────────────────────────────────────────────────


class TestCrossLinks:
    def test_doc_125_references_capability_map(self) -> None:
        text = _c(_DOC_125)
        assert "132_AI_AGENT_PLATFORM_CAPABILITY_MAP.md" in text

    def test_doc_125_references_blockers(self) -> None:
        text = _c(_DOC_125)
        assert "134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md" in text

    def test_doc_125_references_test_audit(self) -> None:
        text = _c(_DOC_125)
        assert "135_TEST_AND_CI_HARDENING_AUDIT.md" in text
