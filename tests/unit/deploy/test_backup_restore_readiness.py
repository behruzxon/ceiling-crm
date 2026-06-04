"""Static validation: backup format and the runbook restore command agree.

The automated backup script produces a PLAIN-SQL gzip dump (`<db>_<ts>.sql.gz`),
so the restore path must be `gunzip -c ... | psql ...`. The deploy runbook
previously documented `pg_dump -F c` + `pg_restore`, which is a custom-format
dump tool and would FAIL on a plain-SQL gzip backup. These tests pin that the
two formats stay consistent and that the restore procedure is safe (throwaway
DB only, never over production).

Offline: reads the backup script + runbook — no Docker, DB, network, or restore.
"""

from __future__ import annotations

from pathlib import Path

_BACKUP = Path("deploy/scripts/backup.sh")
_RUNBOOK = Path("docs/AI_AGENT_SYSTEM/128_PRODUCTION_DEPLOYMENT_RUNBOOK.md")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _command_lines(src: str, needle: str) -> list[str]:
    """Lines that actually invoke `needle` (excludes `#` comments / prose)."""
    return [ln for ln in src.splitlines() if needle in ln and not ln.lstrip().startswith("#")]


# ── backup script: plain-SQL gzip ────────────────────────────────────────────


class TestBackupFormat:
    def test_backup_script_exists(self):
        assert _BACKUP.exists()

    def test_backup_is_plain_sql_gzip(self):
        src = _read(_BACKUP)
        assert "| gzip" in src
        assert ".sql.gz" in src

    def test_pg_dump_command_uses_no_custom_format(self):
        # The actual pg_dump invocation must not use -F/-Fc (custom format),
        # otherwise the gunzip|psql restore path would be wrong.
        for ln in _command_lines(_read(_BACKUP), "pg_dump"):
            assert "-F" not in ln, f"pg_dump uses a format flag (not plain SQL): {ln}"

    def test_backup_header_documents_gunzip_psql_restore(self):
        src = _read(_BACKUP)
        assert "gunzip" in src and "psql" in src  # restore documented in the header


# ── runbook restore matches the backup format ────────────────────────────────


class TestRunbookRestore:
    def test_restore_uses_gunzip_psql(self):
        src = _read(_RUNBOOK)
        assert "gunzip -c" in src
        assert "| psql" in src
        assert ".sql.gz" in src  # restores the same artifact the backup produces

    def test_no_pg_restore_invocation(self):
        # pg_restore may be NAMED in prose (explaining why not to use it) but must
        # never appear as an actual command (a flag-bearing invocation).
        src = _read(_RUNBOOK)
        assert "pg_restore -h" not in src
        assert "pg_restore -d" not in src

    def test_runbook_backup_is_also_plain_sql_gzip(self):
        for ln in _command_lines(_read(_RUNBOOK), "pg_dump"):
            assert "-F c" not in ln and "-Fc" not in ln, f"runbook pg_dump custom format: {ln}"


# ── restore safety: throwaway DB only, never over production ──────────────────


class TestRestoreSafety:
    def test_restore_targets_throwaway_db(self):
        assert "-d ceilingcrm_verify" in _read(_RUNBOOK)

    def test_production_restore_warning_present(self):
        # Collapse markdown line-wrapping before matching the warning sentence.
        norm = " ".join(_read(_RUNBOOK).split()).lower()
        assert "never run the restore against the production" in norm

    def test_restore_psql_does_not_target_live_db(self):
        # Every gunzip|psql restore step must point at the scratch DB.
        for ln in _command_lines(_read(_RUNBOOK), "psql"):
            if "-d ceilingcrm" in ln:
                assert "-d ceilingcrm_verify" in ln, f"restore targets live DB: {ln}"
