"""Tests for Step BK — AdminSecurityAuditService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.services.admin_security_audit_service import AdminSecurityAuditService

svc = AdminSecurityAuditService


def _now():
    return datetime.now(UTC)


def _login(status="success", admin_id="u1", ip="1.2.3.4"):
    return {
        "status": status,
        "admin_id": admin_id,
        "ip_address": ip,
        "created_at": _now().isoformat(),
    }


def _session(status="active", admin_id="u1", ip="1.2.3.4", hours_ago=1, expires_hours=11):
    now = _now()
    return {
        "status": status,
        "admin_id": admin_id,
        "ip_address": ip,
        "created_at": (now - timedelta(hours=hours_ago)).isoformat(),
        "last_seen_at": (now - timedelta(hours=hours_ago)).isoformat(),
        "expires_at": (now + timedelta(hours=expires_hours)).isoformat(),
    }


def _audit(action="rbac.denied", status="denied", actor="u1", reason="", created_at=""):
    return {
        "action": action,
        "status": status,
        "actor_admin_id": actor,
        "reason": reason,
        "created_at": created_at or _now().isoformat(),
        "metadata_json": None,
    }


class TestEmptyDB:
    def test_empty_dashboard(self):
        d = svc.build_security_dashboard([], [], [])
        assert d.login_metrics.total == 0
        assert d.session_metrics.active == 0
        assert d.denied_metrics.total_denied == 0
        assert d.sensitive_metrics.total == 0
        assert d.generated_at != ""

    def test_empty_login_metrics(self):
        m = svc.get_login_attempt_metrics([])
        assert m.total == 0
        assert m.failure_rate == 0.0

    def test_empty_session_metrics(self):
        m = svc.get_session_metrics([])
        assert m.active == 0

    def test_empty_denied(self):
        m = svc.get_permission_denied_metrics([])
        assert m.total_denied == 0

    def test_empty_sensitive(self):
        m = svc.get_sensitive_action_metrics([])
        assert m.total == 0

    def test_empty_recent(self):
        r = svc.get_recent_audit_events([])
        assert r == []

    def test_empty_suspicious(self):
        from core.services.admin_security_audit_service import (
            LoginAttemptMetrics,
            PermissionDeniedMetrics,
            SensitiveActionMetrics,
            SessionMetrics,
        )

        s = svc.detect_suspicious_activity(
            LoginAttemptMetrics(),
            SessionMetrics(),
            PermissionDeniedMetrics(),
            SensitiveActionMetrics(),
        )
        assert s == []


class TestLoginAttemptMetrics:
    def test_total(self):
        m = svc.get_login_attempt_metrics([_login(), _login("failed")])
        assert m.total == 2

    def test_successful(self):
        m = svc.get_login_attempt_metrics([_login("success"), _login("success")])
        assert m.successful == 2

    def test_failed(self):
        m = svc.get_login_attempt_metrics([_login("failed"), _login("failed"), _login("success")])
        assert m.failed == 2

    def test_blocked(self):
        m = svc.get_login_attempt_metrics([_login("blocked")])
        assert m.blocked == 1

    def test_failure_rate(self):
        m = svc.get_login_attempt_metrics([_login("failed"), _login("success")])
        assert m.failure_rate == 0.5

    def test_failure_rate_zero(self):
        m = svc.get_login_attempt_metrics([_login("success")])
        assert m.failure_rate == 0.0

    def test_top_failed_ips(self):
        attempts = [_login("failed", ip="1.1.1.1")] * 3 + [_login("failed", ip="2.2.2.2")]
        m = svc.get_login_attempt_metrics(attempts)
        assert m.top_failed_ips[0][0] == "1.1.1.1"
        assert m.top_failed_ips[0][1] == 3

    def test_top_failed_admin_ids(self):
        attempts = [_login("failed", admin_id="bad1")] * 4 + [_login("failed", admin_id="bad2")]
        m = svc.get_login_attempt_metrics(attempts)
        assert m.top_failed_admin_ids[0][0] == "bad1"

    def test_blocked_counted_in_failed_ips(self):
        attempts = [_login("blocked", ip="5.5.5.5")]
        m = svc.get_login_attempt_metrics(attempts)
        assert m.top_failed_ips[0][1] == 1


class TestSessionMetrics:
    def test_active(self):
        m = svc.get_session_metrics([_session("active"), _session("active")])
        assert m.active == 2

    def test_expired(self):
        m = svc.get_session_metrics([_session("expired")])
        assert m.expired == 1

    def test_revoked(self):
        m = svc.get_session_metrics([_session("revoked")])
        assert m.revoked == 1

    def test_replaced(self):
        m = svc.get_session_metrics([_session("replaced")])
        assert m.replaced == 1

    def test_created_today(self):
        s = _session()
        s["created_at"] = _now().isoformat()
        m = svc.get_session_metrics([s])
        assert m.created_today == 1

    def test_expiring_soon(self):
        s = _session(expires_hours=1)
        m = svc.get_session_metrics([s])
        assert m.expiring_soon == 1

    def test_not_expiring_soon(self):
        s = _session(expires_hours=10)
        m = svc.get_session_metrics([s])
        assert m.expiring_soon == 0

    def test_stale_session(self):
        now = _now()
        s = _session()
        s["last_seen_at"] = (now - timedelta(hours=48)).isoformat()
        m = svc.get_session_metrics([s], now=now)
        assert m.stale == 1

    def test_fresh_session_not_stale(self):
        s = _session()
        s["last_seen_at"] = _now().isoformat()
        m = svc.get_session_metrics([s])
        assert m.stale == 0


class TestPermissionDeniedMetrics:
    def test_total(self):
        m = svc.get_permission_denied_metrics([_audit(status="denied")] * 3)
        assert m.total_denied == 3

    def test_non_denied_excluded(self):
        entries = [_audit(status="success"), _audit(status="denied")]
        m = svc.get_permission_denied_metrics(entries)
        assert m.total_denied == 1

    def test_by_actor(self):
        entries = [_audit(actor="op1"), _audit(actor="op1"), _audit(actor="op2")]
        m = svc.get_permission_denied_metrics(entries)
        assert m.by_actor[0] == ("op1", 2)

    def test_by_action(self):
        entries = [_audit(action="settings.mutate"), _audit(action="settings.mutate")]
        m = svc.get_permission_denied_metrics(entries)
        assert m.by_action[0] == ("settings.mutate", 2)

    def test_last_denied_at(self):
        entries = [
            _audit(created_at="2026-05-26T10:00:00"),
            _audit(created_at="2026-05-26T12:00:00"),
        ]
        m = svc.get_permission_denied_metrics(entries)
        assert "12:00" in m.last_denied_at

    def test_extracts_permission_from_reason(self):
        e = _audit(reason="operator does not have crm.export")
        m = svc.get_permission_denied_metrics([e])
        assert any("crm.export" in p for p, _ in m.by_permission)


class TestSensitiveActionMetrics:
    def test_total(self):
        entries = [_audit(action="crm.reply.send", status="success")]
        m = svc.get_sensitive_action_metrics(entries)
        assert m.total == 1

    def test_non_sensitive_excluded(self):
        entries = [_audit(action="rbac.check", status="success")]
        m = svc.get_sensitive_action_metrics(entries)
        assert m.total == 0

    def test_by_action(self):
        entries = [
            _audit(action="crm.export", status="success"),
            _audit(action="crm.export", status="success"),
            _audit(action="agent.rollout.apply", status="success"),
        ]
        m = svc.get_sensitive_action_metrics(entries)
        assert m.by_action[0] == ("crm.export", 2)

    def test_by_actor(self):
        entries = [_audit(action="crm.reply.send", actor="op1", status="success")]
        m = svc.get_sensitive_action_metrics(entries)
        assert m.by_actor[0][0] == "op1"

    def test_last_action_at(self):
        entries = [
            _audit(
                action="agent.settings.mutate", status="success", created_at="2026-05-26T14:00:00"
            ),
        ]
        m = svc.get_sensitive_action_metrics(entries)
        assert "14:00" in m.last_action_at

    def test_all_sensitive_actions_recognized(self):
        actions = svc.get_sensitive_actions()
        assert len(actions) >= 10
        assert "crm.reply.send" in actions
        assert "agent.rollout.apply" in actions


class TestSuspiciousActivity:
    def _login_metrics(self, **kw):
        from core.services.admin_security_audit_service import LoginAttemptMetrics

        return LoginAttemptMetrics(**kw)

    def _session_metrics(self, **kw):
        from core.services.admin_security_audit_service import SessionMetrics

        return SessionMetrics(**kw)

    def _denied_metrics(self, **kw):
        from core.services.admin_security_audit_service import PermissionDeniedMetrics

        return PermissionDeniedMetrics(**kw)

    def _sensitive_metrics(self, **kw):
        from core.services.admin_security_audit_service import SensitiveActionMetrics

        return SensitiveActionMetrics(**kw)

    def test_brute_force_ip(self):
        lm = self._login_metrics(top_failed_ips=[("1.1.1.1", 6)])
        indicators = svc.detect_suspicious_activity(
            lm,
            self._session_metrics(),
            self._denied_metrics(),
            self._sensitive_metrics(),
        )
        assert any(i.rule == "brute_force_ip" for i in indicators)

    def test_brute_force_admin(self):
        lm = self._login_metrics(top_failed_admin_ids=[("bad_user", 7)])
        indicators = svc.detect_suspicious_activity(
            lm,
            self._session_metrics(),
            self._denied_metrics(),
            self._sensitive_metrics(),
        )
        assert any(i.rule == "brute_force_admin" for i in indicators)

    def test_excessive_denied(self):
        dm = self._denied_metrics(by_actor=[("op1", 15)])
        indicators = svc.detect_suspicious_activity(
            self._login_metrics(),
            self._session_metrics(),
            dm,
            self._sensitive_metrics(),
        )
        assert any(i.rule == "excessive_denied" for i in indicators)

    def test_excessive_export(self):
        sm = self._sensitive_metrics(by_action=[("crm.export", 5)])
        indicators = svc.detect_suspicious_activity(
            self._login_metrics(),
            self._session_metrics(),
            self._denied_metrics(),
            sm,
        )
        assert any(i.rule == "excessive_export" for i in indicators)

    def test_too_many_active_sessions(self):
        sess = self._session_metrics(active=25)
        indicators = svc.detect_suspicious_activity(
            self._login_metrics(),
            sess,
            self._denied_metrics(),
            self._sensitive_metrics(),
        )
        assert any(i.rule == "too_many_active_sessions" for i in indicators)

    def test_stale_sessions(self):
        sess = self._session_metrics(stale=8)
        indicators = svc.detect_suspicious_activity(
            self._login_metrics(),
            sess,
            self._denied_metrics(),
            self._sensitive_metrics(),
        )
        assert any(i.rule == "stale_sessions" for i in indicators)

    def test_multi_ip_session(self):
        sessions = [
            {"status": "active", "admin_id": "u1", "ip_address": "1.1.1.1"},
            {"status": "active", "admin_id": "u1", "ip_address": "2.2.2.2"},
            {"status": "active", "admin_id": "u1", "ip_address": "3.3.3.3"},
        ]
        indicators = svc.detect_suspicious_activity(
            self._login_metrics(),
            self._session_metrics(),
            self._denied_metrics(),
            self._sensitive_metrics(),
            sessions=sessions,
        )
        assert any(i.rule == "multi_ip_session" for i in indicators)

    def test_no_suspicious_below_thresholds(self):
        lm = self._login_metrics(top_failed_ips=[("1.1.1.1", 2)])
        indicators = svc.detect_suspicious_activity(
            lm,
            self._session_metrics(),
            self._denied_metrics(),
            self._sensitive_metrics(),
        )
        assert len(indicators) == 0

    def test_severity_levels(self):
        lm = self._login_metrics(top_failed_ips=[("x", 10)])
        indicators = svc.detect_suspicious_activity(
            lm,
            self._session_metrics(),
            self._denied_metrics(),
            self._sensitive_metrics(),
        )
        assert indicators[0].severity == "high"


class TestRecommendations:
    def _lm(self, **kw):
        from core.services.admin_security_audit_service import LoginAttemptMetrics

        return LoginAttemptMetrics(**kw)

    def _sm(self, **kw):
        from core.services.admin_security_audit_service import SessionMetrics

        return SessionMetrics(**kw)

    def _dm(self, **kw):
        from core.services.admin_security_audit_service import PermissionDeniedMetrics

        return PermissionDeniedMetrics(**kw)

    def test_high_failure_rate(self):
        recs = svc.build_security_recommendations(
            self._lm(total=10, failure_rate=0.5),
            self._sm(),
            self._dm(),
            [],
        )
        assert any(r.priority == "high" for r in recs)

    def test_stale_sessions(self):
        recs = svc.build_security_recommendations(
            self._lm(),
            self._sm(stale=5),
            self._dm(),
            [],
        )
        assert any("stale" in r.title.lower() for r in recs)

    def test_expiring_soon(self):
        recs = svc.build_security_recommendations(
            self._lm(),
            self._sm(expiring_soon=8),
            self._dm(),
            [],
        )
        assert any("tugaydigan" in r.title.lower() for r in recs)

    def test_high_alerts(self):
        from core.services.admin_security_audit_service import SuspiciousIndicator

        alerts = [SuspiciousIndicator(severity="high", rule="brute_force")]
        recs = svc.build_security_recommendations(
            self._lm(),
            self._sm(),
            self._dm(),
            alerts,
        )
        assert any(r.priority == "high" and "shubhali" in r.title.lower() for r in recs)

    def test_many_denied(self):
        recs = svc.build_security_recommendations(
            self._lm(),
            self._sm(),
            self._dm(total_denied=25),
            [],
        )
        assert any("denied" in r.title.lower() for r in recs)

    def test_ok_when_clean(self):
        recs = svc.build_security_recommendations(
            self._lm(),
            self._sm(),
            self._dm(),
            [],
        )
        assert any("yaxshi" in r.title.lower() for r in recs)


class TestRecentEvents:
    def test_sorted_desc(self):
        entries = [
            _audit(created_at="2026-05-26T10:00:00"),
            _audit(created_at="2026-05-26T14:00:00"),
            _audit(created_at="2026-05-26T12:00:00"),
        ]
        r = svc.get_recent_audit_events(entries)
        assert "14:00" in r[0]["created_at"]

    def test_limit(self):
        entries = [_audit() for _ in range(10)]
        r = svc.get_recent_audit_events(entries, limit=3)
        assert len(r) == 3

    def test_sanitized(self):
        e = _audit()
        e["session_id_hash"] = "secret"
        r = svc.get_recent_audit_events([e])
        assert "session_id_hash" not in r[0]


class TestSanitization:
    def test_sanitize_ip(self):
        assert svc.sanitize_ip("1.2.3.4") == "1.2.3.4"
        assert svc.sanitize_ip("") == ""
        assert len(svc.sanitize_ip("x" * 100)) <= 45

    def test_sanitize_admin_id(self):
        assert svc.sanitize_admin_id("user1") == "user1"
        assert len(svc.sanitize_admin_id("x" * 200)) <= 100

    def test_sanitize_user_agent(self):
        assert svc.sanitize_user_agent("Mozilla/5.0") == "Mozilla/5.0"
        assert svc.sanitize_user_agent("") == ""
        assert len(svc.sanitize_user_agent("x" * 500)) <= 200

    def test_user_agent_token_redacted(self):
        ua = svc.sanitize_user_agent("sk-secret123 browser")
        assert "sk-" not in ua

    def test_sanitize_audit_metadata_none(self):
        assert svc.sanitize_audit_metadata(None) is None

    def test_sanitize_audit_metadata_clean(self):
        d = svc.sanitize_audit_metadata({"key": "val"})
        assert d == {"key": "val"}

    def test_sanitize_audit_metadata_token(self):
        d = svc.sanitize_audit_metadata({"tok": "sk-secret"})
        assert "[REDACTED]" in d["tok"]

    def test_sanitize_audit_entry_no_hash(self):
        e = {"session_id_hash": "abc", "action": "test"}
        s = svc.sanitize_audit_entry(e)
        assert "session_id_hash" not in s

    def test_sanitize_audit_entry_reason(self):
        e = {"reason": "sk-secret error"}
        s = svc.sanitize_audit_entry(e)
        assert "sk-" not in s["reason"]


class TestBuildDashboard:
    def test_full_dashboard(self):
        logins = [_login("success"), _login("failed"), _login("blocked")]
        sessions = [_session("active"), _session("expired")]
        audits = [_audit(action="crm.reply.send", status="success"), _audit()]
        d = svc.build_security_dashboard(logins, sessions, audits, period_hours=48)
        assert d.login_metrics.total == 3
        assert d.session_metrics.active == 1
        assert d.sensitive_metrics.total == 1
        assert d.period_hours == 48
        assert d.generated_at != ""
        assert len(d.recommendations) >= 1


class TestImmutability:
    def test_login_metrics_frozen(self):
        import pytest

        from core.services.admin_security_audit_service import LoginAttemptMetrics

        m = LoginAttemptMetrics()
        with pytest.raises(AttributeError):
            m.total = 5  # type: ignore[misc]

    def test_session_metrics_frozen(self):
        import pytest

        from core.services.admin_security_audit_service import SessionMetrics

        m = SessionMetrics()
        with pytest.raises(AttributeError):
            m.active = 5  # type: ignore[misc]

    def test_dashboard_frozen(self):
        import pytest

        from core.services.admin_security_audit_service import SecurityDashboard

        d = SecurityDashboard()
        with pytest.raises(AttributeError):
            d.period_hours = 48  # type: ignore[misc]

    def test_indicator_frozen(self):
        import pytest

        from core.services.admin_security_audit_service import SuspiciousIndicator

        i = SuspiciousIndicator()
        with pytest.raises(AttributeError):
            i.rule = "x"  # type: ignore[misc]

    def test_recommendation_frozen(self):
        import pytest

        from core.services.admin_security_audit_service import SecurityRecommendation

        r = SecurityRecommendation()
        with pytest.raises(AttributeError):
            r.title = "x"  # type: ignore[misc]
