"""Step 13 — Production deployment runbook docs tests."""

from __future__ import annotations

import re
from pathlib import Path

_DOC_128 = "docs/AI_AGENT_SYSTEM/128_PRODUCTION_DEPLOYMENT_RUNBOOK.md"
_DOC_129 = "docs/AI_AGENT_SYSTEM/129_STAGE_1_LOCAL_DRY_RUN_CHECK.md"


def _c(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _all() -> str:
    return _c(_DOC_128) + "\n" + _c(_DOC_129)


class TestDocsExist:
    def test_doc_128_exists(self) -> None:
        assert Path(_DOC_128).exists()

    def test_doc_129_exists(self) -> None:
        assert Path(_DOC_129).exists()

    def test_doc_128_non_empty(self) -> None:
        assert len(_c(_DOC_128)) > 2000

    def test_doc_129_non_empty(self) -> None:
        assert len(_c(_DOC_129)) > 800


class TestRunbookContent:
    def test_purpose_section(self) -> None:
        assert "Purpose" in _c(_DOC_128)

    def test_preconditions_section(self) -> None:
        assert "Preconditions" in _c(_DOC_128)

    def test_required_services_section(self) -> None:
        assert "Required services" in _c(_DOC_128)

    def test_env_groups_section(self) -> None:
        assert "Required env groups" in _c(_DOC_128)

    def test_backup_procedure_section(self) -> None:
        text = _c(_DOC_128)
        assert "Backup procedure" in text
        assert "pg_dump" in text

    def test_restore_verification(self) -> None:
        text = _c(_DOC_128)
        assert "pg_restore" in text
        assert "verification" in text.lower() or "verify" in text.lower()

    def test_migration_section(self) -> None:
        text = _c(_DOC_128)
        assert "Migration procedure" in text
        assert "alembic upgrade head" in text
        assert "alembic current" in text

    def test_deploy_sequence(self) -> None:
        assert "Deploy sequence" in _c(_DOC_128)

    def test_smoke_checks(self) -> None:
        text = _c(_DOC_128)
        assert "Smoke checks" in text
        assert "/healthz" in text

    def test_observation_section(self) -> None:
        text = _c(_DOC_128)
        assert "Observation" in text
        assert "30 min" in text or "30-minute" in text

    def test_rollback_section(self) -> None:
        text = _c(_DOC_128)
        assert "Rollback" in text
        assert "emergency stop" in text.lower() or "Emergency stop" in text

    def test_do_not_do_section(self) -> None:
        text = _c(_DOC_128)
        assert "Do-not-do" in text or "Do not" in text


class TestStage1Flags:
    def test_decision_engine_enabled(self) -> None:
        assert "AGENT_DECISION_ENGINE_ENABLED=true" in _c(_DOC_128)

    def test_decision_log_only(self) -> None:
        assert "AGENT_DECISION_LOG_ONLY=true" in _c(_DOC_128)


class TestMustOffFlags:
    def test_live_sender_off(self) -> None:
        assert "AGENT_EXECUTION_LIVE_SENDER_ENABLED" in _c(_DOC_128)

    def test_campaign_send_off(self) -> None:
        assert "CRM_CAMPAIGN_SEND_ENABLED" in _c(_DOC_128)

    def test_followups_off(self) -> None:
        assert "AGENT_FOLLOWUPS_ENABLED" in _c(_DOC_128)

    def test_operator_reply_off(self) -> None:
        assert "CRM_OPERATOR_REPLY_ENABLED" in _c(_DOC_128)

    def test_digest_delivery_off(self) -> None:
        assert "CRM_OPERATOR_DIGEST_DELIVERY_ENABLED" in _c(_DOC_128)

    def test_security_actions_off(self) -> None:
        assert "ADMIN_SECURITY_ACTIONS_ENABLED" in _c(_DOC_128)

    def test_ip_enforcement_off(self) -> None:
        assert "ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED" in _c(_DOC_128)

    def test_auto_execute_off(self) -> None:
        assert "AGENT_EXECUTION_AUTO_EXECUTE_APPROVED" in _c(_DOC_128)


class TestDryRunDoc:
    def test_dryrun_guide_command(self) -> None:
        assert "production_deploy_dry_run_check.py" in _c(_DOC_129)

    def test_dryrun_guide_json_mode(self) -> None:
        assert "--json" in _c(_DOC_129)

    def test_dryrun_severities(self) -> None:
        text = _c(_DOC_129)
        assert "GREEN" in text and "YELLOW" in text and "RED" in text

    def test_dryrun_no_db(self) -> None:
        text = _c(_DOC_129).lower()
        assert "does not connect to postgresql" in text or "does not connect to db" in text

    def test_dryrun_no_telegram(self) -> None:
        assert "does not call the telegram" in _c(_DOC_129).lower()

    def test_dryrun_no_openai(self) -> None:
        assert "does not call the openai" in _c(_DOC_129).lower()

    def test_dryrun_no_alembic(self) -> None:
        assert "alembic upgrade" in _c(_DOC_129).lower()
        assert "does not run" in _c(_DOC_129).lower()


class TestStatusContract:
    def test_runbook_says_deploy_no(self) -> None:
        text = _c(_DOC_128)
        assert "Deploy: NO" in text

    def test_runbook_says_vps_no(self) -> None:
        text = _c(_DOC_128)
        assert "VPS: NO" in text

    def test_runbook_says_stage1_not_applied(self) -> None:
        text = _c(_DOC_128)
        # Strip markdown blockquote markers and collapse whitespace, since
        # the literal "NOT APPLIED" wraps across the blockquote at the top.
        stripped = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
        normalized = " ".join(stripped.split())
        assert "NOT APPLIED" in normalized

    def test_runbook_says_flags_not_enabled(self) -> None:
        text = _c(_DOC_128)
        assert "NOT ENABLED" in text


class TestNoSecretLeaks:
    def test_no_bot_token_format(self) -> None:
        assert not re.search(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", _all())

    def test_no_openai_key(self) -> None:
        # The docs may mention `sk-…` as a placeholder pattern to ban. Forbid
        # only real-looking tokens (≥20 chars after `sk-`).
        assert not re.search(r"sk-[A-Za-z0-9]{20,}", _all())
        # Allow placeholder env definitions like OPENAI_API_KEY=<random> or
        # OPENAI_API_KEY=changeme but never a real key.
        assert not re.search(r"OPENAI_API_KEY=[A-Za-z0-9_-]{20,}", _all())

    def test_no_bearer_literal(self) -> None:
        assert "Bearer " not in _all()

    def test_no_db_url_with_password(self) -> None:
        text = _all()
        assert "postgresql+asyncpg://" not in text
        # Plain string mention is okay if it's a placeholder, not a real URL
        # with creds. We at least confirm no `user:pass@host` form is embedded.
        assert not re.search(r"postgresql://[^@\s]+:[^@\s]+@", text)

    def test_no_aws_key_literal(self) -> None:
        assert not re.search(r"AKIA[0-9A-Z]{16}", _all())
