"""Static validation: production migrations run exactly once (no Alembic race).

Before this fix every service shared an ENTRYPOINT that ran
``alembic upgrade head`` on start, so bot/scheduler/celery-worker migrated
concurrently on first deploy (lock/race/schema-drift risk).

Design (least-risk for this repo):
  - entrypoint.sh gates migrations behind RUN_MIGRATIONS (default "true", so
    local/dev keeps auto-migrating and nothing else changes),
  - a dedicated one-shot ``migrate`` service runs migrations once and exits,
  - bot/scheduler/celery-worker set RUN_MIGRATIONS=false and wait for
    ``migrate`` via depends_on: condition: service_completed_successfully.

Offline: parses YAML / reads the entrypoint — no Docker, DB, or migrations run.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_PROD = Path("docker-compose.prod.yml")
_DEV = Path("docker-compose.yml")
_ENTRYPOINT = Path("deploy/docker/entrypoint.sh")

# Services that build from the app image and therefore run entrypoint.sh.
_PROD_IMAGE_SERVICES = ("migrate", "bot", "scheduler", "celery-worker")


def _services(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["services"]


def _run_migrations(service: dict) -> str:
    """Effective RUN_MIGRATIONS for a service (default 'true' when unset)."""
    return str((service.get("environment") or {}).get("RUN_MIGRATIONS", "true"))


def _depends(service: dict) -> dict:
    return {k: (v or {}).get("condition") for k, v in (service.get("depends_on") or {}).items()}


# ── entrypoint gates migrations behind the flag ───────────────────────────────


class TestEntrypointFlag:
    def test_entrypoint_honors_run_migrations(self):
        src = _ENTRYPOINT.read_text(encoding="utf-8")
        assert "RUN_MIGRATIONS" in src
        assert "alembic upgrade head" in src
        # the migration must be conditional, not unconditional
        assert "if [" in src and "RUN_MIGRATIONS" in src

    def test_default_preserves_auto_migration(self):
        # Default "true" keeps local/dev behavior (auto-migrate) unchanged.
        src = _ENTRYPOINT.read_text(encoding="utf-8")
        assert "RUN_MIGRATIONS:-true" in src


# ── prod runs migrations exactly once via a dedicated one-shot service ─────────


class TestProdSingleMigrator:
    def test_migrate_service_exists_and_is_one_shot(self):
        migrate = _services(_PROD)["migrate"]
        assert _run_migrations(migrate) != "false"
        assert migrate.get("restart") == "no"  # one-shot, must not respawn
        # depends on the DB being ready before migrating
        assert _depends(migrate).get("postgres") == "service_healthy"

    def test_exactly_one_service_migrates(self):
        svcs = _services(_PROD)
        migrators = [
            name
            for name in _PROD_IMAGE_SERVICES
            if _run_migrations(svcs[name]).lower() not in ("false", "0")
        ]
        assert migrators == ["migrate"], f"expected only 'migrate', got {migrators}"

    def test_long_running_services_skip_migrations(self):
        svcs = _services(_PROD)
        for name in ("bot", "scheduler", "celery-worker"):
            assert _run_migrations(svcs[name]) == "false", f"{name} should not migrate"

    def test_long_running_services_wait_for_migrate(self):
        svcs = _services(_PROD)
        for name in ("bot", "scheduler", "celery-worker"):
            assert (
                _depends(svcs[name]).get("migrate") == "service_completed_successfully"
            ), f"{name} must wait for migrate to complete"


# ── dev/local behavior preserved (still auto-migrates, no migrate service) ─────


class TestDevUnchanged:
    def test_dev_has_no_migrate_service(self):
        assert "migrate" not in _services(_DEV)

    def test_dev_services_still_auto_migrate(self):
        # No dev service disables migrations → entrypoint default (true) runs them.
        svcs = _services(_DEV)
        for name, svc in svcs.items():
            assert _run_migrations(svc) != "false", f"dev {name} unexpectedly disabled migrations"
