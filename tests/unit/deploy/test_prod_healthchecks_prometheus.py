"""Static validation of prod healthchecks + Prometheus scrape consistency.

Reliability fixes:
  - Dockerfile HEALTHCHECK must inspect check_database_health()'s status and
    exit non-zero on failure (the old form ignored the return → always healthy).
  - docker-compose.prod.yml bot/scheduler/celery-worker must each carry a
    meaningful (not always-pass) healthcheck.
  - Prometheus must scrape the port the bot actually serves /metrics on in
    production (webhook mode → 8080), not the dev-polling 9090 port.
  - Dev/local must stay unchanged (polling exposes 9090).

Offline: parses YAML / reads files — no Docker, network, DB, or services.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_PROD = Path("docker-compose.prod.yml")
_DEV = Path("docker-compose.yml")
_PROM = Path("deploy/docker/prometheus/prometheus.yml")
_DOCKERFILE = Path("deploy/docker/Dockerfile")


def _compose(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _healthcheck_test(service: dict) -> str:
    hc = service.get("healthcheck")
    assert hc, "service has no healthcheck block"
    test = hc["test"]
    # test is ["CMD-SHELL", "<cmd>"] or ["CMD", ...]
    return " ".join(test) if isinstance(test, list) else str(test)


# ── Prometheus scrape target matches the prod runtime (webhook → 8080) ────────


class TestPrometheusScrapeTarget:
    def test_target_is_bot_8080(self):
        cfg = yaml.safe_load(_PROM.read_text(encoding="utf-8"))
        targets = cfg["scrape_configs"][0]["static_configs"][0]["targets"]
        assert targets == ["bot:8080"], f"expected bot:8080, got {targets}"

    def test_not_scraping_9090(self):
        assert "bot:9090" not in _PROM.read_text(encoding="utf-8")

    def test_metrics_path_unchanged(self):
        cfg = yaml.safe_load(_PROM.read_text(encoding="utf-8"))
        assert cfg["scrape_configs"][0]["metrics_path"] == "/metrics"


# ── Prod compose: every long-running service has a real healthcheck ───────────


class TestProdHealthchecks:
    def test_bot_uses_http_health_on_8080(self):
        test = _healthcheck_test(_compose(_PROD)["services"]["bot"])
        assert "/health" in test
        assert "8080" in test
        assert "9090" not in test  # prod bot is webhook, not polling

    def test_scheduler_probes_real_db(self):
        test = _healthcheck_test(_compose(_PROD)["services"]["scheduler"])
        # meaningful: derives exit code from DB health status, not always-pass
        assert "check_database_health" in test
        assert "sys.exit" in test

    def test_celery_worker_pings_broker(self):
        test = _healthcheck_test(_compose(_PROD)["services"]["celery-worker"])
        assert "inspect ping" in test

    def test_all_long_running_services_have_healthchecks(self):
        services = _compose(_PROD)["services"]
        for name in ("postgres", "redis", "bot", "scheduler", "celery-worker"):
            assert services[name].get("healthcheck"), f"{name} missing healthcheck"


# ── Dockerfile default healthcheck is no longer always-pass ───────────────────


class TestDockerfileHealthcheck:
    def test_healthcheck_inspects_status_and_exits(self):
        src = _DOCKERFILE.read_text(encoding="utf-8")
        assert "check_database_health" in src
        assert "sys.exit" in src
        assert "'ok'" in src or '"ok"' in src

    def test_old_always_pass_form_gone(self):
        # The old form called the coroutine and discarded the result, relying on
        # "|| exit 1" which never fired because the call never raised.
        src = _DOCKERFILE.read_text(encoding="utf-8")
        assert "check_database_health()) || exit 1" not in src


# ── Dev/local must stay on the polling port (unchanged) ───────────────────────


class TestDevUnchanged:
    def test_dev_bot_healthcheck_still_9090(self):
        test = _healthcheck_test(_compose(_DEV)["services"]["bot"])
        assert "9090/health" in test or "9090" in test
        assert "/health" in test
