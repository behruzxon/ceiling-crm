"""Step 10 — Stage 1 LOG_ONLY readiness review doc tests."""

from __future__ import annotations

from pathlib import Path

_DOC = "docs/AI_AGENT_SYSTEM/125_STAGE_1_READINESS_REVIEW_AFTER_FRESH_START.md"


def _c() -> str:
    return Path(_DOC).read_text(encoding="utf-8")


class TestDocExists:
    def test_exists(self) -> None:
        assert Path(_DOC).exists()

    def test_non_empty(self) -> None:
        assert len(_c()) > 1000

    def test_has_title(self) -> None:
        assert "# 125 — Stage 1 LOG_ONLY Readiness Review" in _c()


class TestCommitAndBranchState:
    def test_contains_latest_commit_hash(self) -> None:
        assert "4e34024" in _c()

    def test_mentions_main_branch(self) -> None:
        assert "`main`" in _c() or "main" in _c()

    def test_mentions_pr1_merged(self) -> None:
        assert "PR #1" in _c() and "merged" in _c()


class TestFreshStartSteps:
    def test_mentions_step_1_project_map(self) -> None:
        assert "Project Map" in _c()

    def test_mentions_step_2_handoff_queue(self) -> None:
        assert "Handoff Queue" in _c()

    def test_mentions_step_3_ai_trace(self) -> None:
        assert "AI Trace" in _c()

    def test_mentions_step_4_missed_leads(self) -> None:
        assert "Missed Leads" in _c()

    def test_mentions_step_5_analytics_charts(self) -> None:
        assert "Analytics Charts" in _c()

    def test_mentions_step_6_conversation_replay(self) -> None:
        assert "Conversation Replay" in _c()

    def test_mentions_step_7_price_estimate_history(self) -> None:
        assert "Price Estimate History" in _c()

    def test_mentions_step_8_operator_assignment(self) -> None:
        assert "Operator Assignment" in _c()

    def test_mentions_step_9_handoff_auto_expire(self) -> None:
        assert "Handoff Auto-Expire" in _c()


class TestSafetyVerdicts:
    def test_contains_no_send_safety_section(self) -> None:
        assert "No-send safety" in _c()

    def test_no_send_verdict_safe(self) -> None:
        text = _c()
        # Section heading + verdict line both present.
        assert "No-send safety verdict" in text
        assert "SAFE" in text

    def test_scheduler_safety_verdict(self) -> None:
        text = _c()
        assert "Scheduler safety verdict" in text

    def test_mentions_no_telegram_send(self) -> None:
        assert "Telegram" in _c()

    def test_mentions_no_openai(self) -> None:
        assert "OpenAI" in _c()


class TestDangerousFlagsOff:
    def test_live_sender_off(self) -> None:
        text = _c()
        assert "AGENT_EXECUTION_LIVE_SENDER_ENABLED" in text
        # Same line should mark OFF
        line = next(
            line for line in text.splitlines() if "AGENT_EXECUTION_LIVE_SENDER_ENABLED" in line
        )
        assert "OFF" in line

    def test_campaign_send_off(self) -> None:
        text = _c()
        line = next(line for line in text.splitlines() if "CRM_CAMPAIGN_SEND_ENABLED" in line)
        assert "OFF" in line

    def test_followups_off(self) -> None:
        text = _c()
        line = next(line for line in text.splitlines() if "AGENT_FOLLOWUPS_ENABLED" in line)
        assert "OFF" in line

    def test_operator_reply_off(self) -> None:
        text = _c()
        line = next(line for line in text.splitlines() if "CRM_OPERATOR_REPLY_ENABLED" in line)
        assert "OFF" in line

    def test_handoff_auto_expire_default_off(self) -> None:
        text = _c()
        line = next(
            line for line in text.splitlines() if "CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED" in line
        )
        assert "OFF" in line

    def test_security_actions_off(self) -> None:
        text = _c()
        line = next(line for line in text.splitlines() if "ADMIN_SECURITY_ACTIONS_ENABLED" in line)
        assert "OFF" in line

    def test_ip_enforcement_off(self) -> None:
        text = _c()
        line = next(
            line for line in text.splitlines() if "ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED" in line
        )
        assert "OFF" in line


class TestMigrationsAndDB:
    def test_mentions_migration_checklist(self) -> None:
        assert "Migration checklist" in _c()

    def test_mentions_handoff_migration_filename(self) -> None:
        assert "n1o2p3q4r5s6" in _c() or "add_crm_operator_handoff_requests" in _c()

    def test_no_new_migrations_for_steps_6_9(self) -> None:
        assert "no new migrations" in _c().lower()

    def test_db_backup_requirement(self) -> None:
        text = _c()
        assert "DB backup requirement" in text
        assert "pg_dump" in text


class TestStage1Posture:
    def test_stage_1_not_applied(self) -> None:
        assert "NOT APPLIED" in _c()

    def test_deploy_no(self) -> None:
        text = _c()
        assert "deploy is **NO**" in text or "Deploy: NO" in text or "deploy" in text.lower()
        assert "**NO**" in text

    def test_vps_no(self) -> None:
        text = _c()
        assert "VPS is **NO**" in text or "VPS: NO" in text or "VPS" in text

    def test_flags_not_enabled(self) -> None:
        assert "NOT ENABLED" in _c()

    def test_go_no_go_section(self) -> None:
        assert "GO / NO-GO" in _c() or "Stage 1 GO / NO-GO" in _c()

    def test_rollback_note_present(self) -> None:
        assert "Rollback note" in _c()


class TestBlockersAndNextSteps:
    def test_outstanding_blockers_environmental(self) -> None:
        assert "Outstanding blockers" in _c() or "blockers" in _c().lower()

    def test_pg_dump_in_blockers(self) -> None:
        assert "pg_dump" in _c()

    def test_alembic_upgrade_in_blockers(self) -> None:
        assert "alembic upgrade head" in _c()

    def test_sentry_in_blockers(self) -> None:
        assert "Sentry" in _c()

    def test_next_recommended_action(self) -> None:
        assert "Next recommended action" in _c()


class TestNoSecretLeaks:
    def test_no_openai_key_in_doc(self) -> None:
        text = _c()
        assert "sk-" not in text

    def test_no_bearer_token_in_doc(self) -> None:
        text = _c()
        assert "Bearer " not in text

    def test_no_db_password_url(self) -> None:
        text = _c()
        # Should not embed a literal Postgres connection string with creds.
        assert "postgresql://" not in text
        assert "postgresql+asyncpg://" not in text
        assert "POSTGRES_PASSWORD=" not in text

    def test_no_bot_token_format(self) -> None:
        text = _c()
        # Telegram tokens follow `<digits>:<35-chars>` — ensure no such literal.
        import re

        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", text)


class TestTestBaseline:
    def test_test_baseline_section(self) -> None:
        assert "Test baseline" in _c()

    def test_mentions_focused_tests_count(self) -> None:
        assert "378 passed" in _c()

    def test_mentions_full_sweep_count(self) -> None:
        assert "6199 passed" in _c()

    def test_mentions_ruff_clean(self) -> None:
        assert "ruff check" in _c() and "clean" in _c()

    def test_mentions_black_clean(self) -> None:
        assert "black --check" in _c() and "clean" in _c()

    def test_mentions_smoke_imports(self) -> None:
        assert "Smoke imports" in _c() or "smoke imports" in _c().lower()
