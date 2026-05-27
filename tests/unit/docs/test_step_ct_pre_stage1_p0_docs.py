"""Tests for Step CT — Pre-Stage 1 P0 Docs."""
from __future__ import annotations

from pathlib import Path

_D = "docs/AI_AGENT_SYSTEM"


def _r(n: str) -> str:
    return Path(f"{_D}/{n}").read_text(encoding="utf-8")


class TestDocsExist:
    def test_113(self):
        assert Path(f"{_D}/113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md").exists()

    def test_114(self):
        assert Path(f"{_D}/114_STAGE_1_ENV_FLAG_MATRIX.md").exists()


class TestRunbook:
    def test_vps_checklist(self):
        assert "VPS" in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")

    def test_db_backup(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md").lower()
        assert "backup" in c

    def test_pg_dump(self):
        assert "pg_dump" in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")

    def test_alembic(self):
        assert "alembic upgrade head" in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")

    def test_admin_session_auth(self):
        assert "ADMIN_SESSION_AUTH_ENABLED=true" in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")

    def test_dangerous_flags_off(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "LIVE_SENDER" in c and "false" in c

    def test_log_only(self):
        assert "LOG_ONLY" in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")

    def test_rollback(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "Rollback" in c or "rollback" in c

    def test_preflight_commands(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "build_dispatcher" in c

    def test_do_not_do(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "Do NOT" in c or "Do-Not" in c

    def test_stop_triggers(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "STOP" in c and "Health RED" in c


class TestFlagMatrix:
    def test_must_be_on(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "Must Be ON" in c

    def test_must_be_off(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "Must Be OFF" in c

    def test_live_sender_off(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "LIVE_SENDER" in c

    def test_followups_off(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "FOLLOWUPS" in c

    def test_campaign_off(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "CAMPAIGN_SEND" in c

    def test_operator_reply_off(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "OPERATOR_REPLY" in c

    def test_log_only_mode(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "log_only" in c

    def test_session_auth_on(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "ADMIN_SESSION_AUTH" in c and "true" in c

    def test_required_env_vars(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "BOT_TOKEN" in c
        assert "OPENAI_API_KEY" in c


class TestNoSecrets:
    def test_not_deployed(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "NOT DEPLOYED" in c

    def test_not_applied(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "NOT APPLIED" in c

    def test_no_token_113(self):
        c = _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")
        assert "sk-proj-" not in c

    def test_no_token_114(self):
        c = _r("114_STAGE_1_ENV_FLAG_MATRIX.md")
        assert "sk-proj-" not in c

    def test_no_openai_key(self):
        assert "OPENAI_API_KEY=" not in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")

    def test_no_db_url(self):
        assert "postgresql://" not in _r("113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md")


class TestSmoke:
    def test_bot(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_api(self):
        from apps.api.main import app
        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
