"""
core.services.admin_security_audit_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only security audit analytics. Pure functions — no DB I/O.
Accepts pre-queried data dicts and produces dashboard metrics.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")

_SENSITIVE_ACTIONS = frozenset({
    "crm.reply.send", "crm.export",
    "report.delivery.approve", "report.delivery.send",
    "agent.rollout.apply", "agent.settings.mutate",
    "agent.execution.approve", "agent.execution.reject",
    "admin_user.create", "admin_user.change_role",
    "admin_user.disable", "admin_user.delete",
})


@dataclass(frozen=True)
class LoginAttemptMetrics:
    total: int = 0
    successful: int = 0
    failed: int = 0
    blocked: int = 0
    failure_rate: float = 0.0
    top_failed_admin_ids: list[tuple[str, int]] = field(default_factory=list)
    top_failed_ips: list[tuple[str, int]] = field(default_factory=list)


@dataclass(frozen=True)
class SessionMetrics:
    active: int = 0
    expired: int = 0
    revoked: int = 0
    replaced: int = 0
    created_today: int = 0
    expiring_soon: int = 0
    stale: int = 0


@dataclass(frozen=True)
class PermissionDeniedMetrics:
    total_denied: int = 0
    by_permission: list[tuple[str, int]] = field(default_factory=list)
    by_actor: list[tuple[str, int]] = field(default_factory=list)
    by_action: list[tuple[str, int]] = field(default_factory=list)
    last_denied_at: str = ""


@dataclass(frozen=True)
class SensitiveActionMetrics:
    total: int = 0
    by_action: list[tuple[str, int]] = field(default_factory=list)
    by_actor: list[tuple[str, int]] = field(default_factory=list)
    last_action_at: str = ""


@dataclass(frozen=True)
class SuspiciousIndicator:
    rule: str = ""
    severity: str = "warning"
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SecurityRecommendation:
    priority: str = "medium"
    title: str = ""
    description: str = ""


@dataclass(frozen=True)
class SecurityDashboard:
    login_metrics: LoginAttemptMetrics = field(default_factory=LoginAttemptMetrics)
    session_metrics: SessionMetrics = field(default_factory=SessionMetrics)
    denied_metrics: PermissionDeniedMetrics = field(default_factory=PermissionDeniedMetrics)
    sensitive_metrics: SensitiveActionMetrics = field(default_factory=SensitiveActionMetrics)
    suspicious: list[SuspiciousIndicator] = field(default_factory=list)
    recommendations: list[SecurityRecommendation] = field(default_factory=list)
    generated_at: str = ""
    period_hours: int = 24


class AdminSecurityAuditService:
    """Read-only security audit analytics. Pure functions."""

    @staticmethod
    def get_sensitive_actions() -> frozenset[str]:
        return _SENSITIVE_ACTIONS

    @staticmethod
    def get_login_attempt_metrics(
        attempts: list[dict[str, Any]],
    ) -> LoginAttemptMetrics:
        if not attempts:
            return LoginAttemptMetrics()
        total = len(attempts)
        successful = sum(1 for a in attempts if a.get("status") == "success")
        failed = sum(1 for a in attempts if a.get("status") == "failed")
        blocked = sum(1 for a in attempts if a.get("status") == "blocked")
        rate = failed / total if total > 0 else 0.0
        fail_by_admin: dict[str, int] = {}
        fail_by_ip: dict[str, int] = {}
        for a in attempts:
            if a.get("status") in ("failed", "blocked"):
                aid = a.get("admin_id", "")
                if aid:
                    fail_by_admin[aid] = fail_by_admin.get(aid, 0) + 1
                ip = a.get("ip_address", "")
                if ip:
                    fail_by_ip[ip] = fail_by_ip.get(ip, 0) + 1
        top_admins = sorted(fail_by_admin.items(), key=lambda x: x[1], reverse=True)[:10]
        top_ips = sorted(fail_by_ip.items(), key=lambda x: x[1], reverse=True)[:10]
        return LoginAttemptMetrics(
            total=total, successful=successful, failed=failed, blocked=blocked,
            failure_rate=round(rate, 3),
            top_failed_admin_ids=[(AdminSecurityAuditService.sanitize_admin_id(a), c) for a, c in top_admins],
            top_failed_ips=[(AdminSecurityAuditService.sanitize_ip(ip), c) for ip, c in top_ips],
        )

    @staticmethod
    def get_session_metrics(
        sessions: list[dict[str, Any]],
        now: datetime | None = None,
    ) -> SessionMetrics:
        if not sessions:
            return SessionMetrics()
        check_time = now or datetime.now(timezone.utc)
        today_start = check_time.replace(hour=0, minute=0, second=0, microsecond=0)
        soon_threshold = check_time + timedelta(hours=2)
        stale_threshold = check_time - timedelta(hours=24)
        active = expired = revoked = replaced = created_today = expiring_soon = stale = 0
        for s in sessions:
            st = s.get("status", "")
            if st == "active":
                active += 1
            elif st == "expired":
                expired += 1
            elif st == "revoked":
                revoked += 1
            elif st == "replaced":
                replaced += 1
            created = s.get("created_at", "")
            if created:
                try:
                    ct = _parse_dt(created)
                    if ct and ct >= today_start:
                        created_today += 1
                except (ValueError, TypeError):
                    pass
            if st == "active":
                exp = s.get("expires_at", "")
                if exp:
                    try:
                        et = _parse_dt(exp)
                        if et and et <= soon_threshold:
                            expiring_soon += 1
                    except (ValueError, TypeError):
                        pass
                last = s.get("last_seen_at", "")
                if last:
                    try:
                        lt = _parse_dt(last)
                        if lt and lt < stale_threshold:
                            stale += 1
                    except (ValueError, TypeError):
                        pass
        return SessionMetrics(
            active=active, expired=expired, revoked=revoked, replaced=replaced,
            created_today=created_today, expiring_soon=expiring_soon, stale=stale,
        )

    @staticmethod
    def get_permission_denied_metrics(
        audit_entries: list[dict[str, Any]],
    ) -> PermissionDeniedMetrics:
        denied = [e for e in audit_entries if e.get("status") == "denied"]
        if not denied:
            return PermissionDeniedMetrics()
        by_perm: dict[str, int] = {}
        by_actor: dict[str, int] = {}
        by_action: dict[str, int] = {}
        last_at = ""
        for e in denied:
            action = e.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1
            actor = e.get("actor_admin_id", "unknown")
            by_actor[actor] = by_actor.get(actor, 0) + 1
            reason = e.get("reason", "")
            perm = _extract_permission_from_reason(reason) or action
            by_perm[perm] = by_perm.get(perm, 0) + 1
            cat = e.get("created_at", "")
            if cat and cat > last_at:
                last_at = cat
        return PermissionDeniedMetrics(
            total_denied=len(denied),
            by_permission=sorted(by_perm.items(), key=lambda x: x[1], reverse=True)[:10],
            by_actor=sorted(by_actor.items(), key=lambda x: x[1], reverse=True)[:10],
            by_action=sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:10],
            last_denied_at=last_at,
        )

    @staticmethod
    def get_sensitive_action_metrics(
        audit_entries: list[dict[str, Any]],
    ) -> SensitiveActionMetrics:
        sensitive = [e for e in audit_entries if e.get("action", "") in _SENSITIVE_ACTIONS]
        if not sensitive:
            return SensitiveActionMetrics()
        by_action: dict[str, int] = {}
        by_actor: dict[str, int] = {}
        last_at = ""
        for e in sensitive:
            action = e.get("action", "")
            by_action[action] = by_action.get(action, 0) + 1
            actor = e.get("actor_admin_id", "unknown")
            by_actor[actor] = by_actor.get(actor, 0) + 1
            cat = e.get("created_at", "")
            if cat and cat > last_at:
                last_at = cat
        return SensitiveActionMetrics(
            total=len(sensitive),
            by_action=sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:10],
            by_actor=sorted(by_actor.items(), key=lambda x: x[1], reverse=True)[:10],
            last_action_at=last_at,
        )

    @staticmethod
    def detect_suspicious_activity(
        login_metrics: LoginAttemptMetrics,
        session_metrics: SessionMetrics,
        denied_metrics: PermissionDeniedMetrics,
        sensitive_metrics: SensitiveActionMetrics,
        sessions: list[dict[str, Any]] | None = None,
    ) -> list[SuspiciousIndicator]:
        indicators: list[SuspiciousIndicator] = []
        for ip, count in login_metrics.top_failed_ips:
            if count >= 5:
                indicators.append(SuspiciousIndicator(
                    rule="brute_force_ip", severity="high",
                    description=f"IP {ip} dan {count} marta failed login",
                    details={"ip": ip, "count": count},
                ))
        for aid, count in login_metrics.top_failed_admin_ids:
            if count >= 5:
                indicators.append(SuspiciousIndicator(
                    rule="brute_force_admin", severity="high",
                    description=f"Admin {aid} uchun {count} marta failed login",
                    details={"admin_id": aid, "count": count},
                ))
        for actor, count in denied_metrics.by_actor:
            if count >= 10:
                indicators.append(SuspiciousIndicator(
                    rule="excessive_denied", severity="medium",
                    description=f"Actor {actor} {count} marta permission denied",
                    details={"actor": actor, "count": count},
                ))
        for action, count in sensitive_metrics.by_action:
            if action == "crm.export" and count >= 3:
                indicators.append(SuspiciousIndicator(
                    rule="excessive_export", severity="medium",
                    description=f"Export {count} marta bajarildi",
                    details={"action": action, "count": count},
                ))
        if session_metrics.active > 20:
            indicators.append(SuspiciousIndicator(
                rule="too_many_active_sessions", severity="warning",
                description=f"{session_metrics.active} ta active session mavjud",
                details={"count": session_metrics.active},
            ))
        if session_metrics.stale > 5:
            indicators.append(SuspiciousIndicator(
                rule="stale_sessions", severity="warning",
                description=f"{session_metrics.stale} ta stale session (24h+ inactive)",
                details={"count": session_metrics.stale},
            ))
        if sessions:
            admin_ips: dict[str, set[str]] = {}
            for s in sessions:
                if s.get("status") == "active":
                    aid = s.get("admin_id", "")
                    ip = s.get("ip_address", "")
                    if aid and ip:
                        admin_ips.setdefault(aid, set()).add(ip)
            for aid, ips in admin_ips.items():
                if len(ips) >= 3:
                    indicators.append(SuspiciousIndicator(
                        rule="multi_ip_session", severity="medium",
                        description=f"Admin {aid} {len(ips)} xil IP'dan active session",
                        details={"admin_id": aid, "ip_count": len(ips)},
                    ))
        return indicators

    @staticmethod
    def build_security_recommendations(
        login_metrics: LoginAttemptMetrics,
        session_metrics: SessionMetrics,
        denied_metrics: PermissionDeniedMetrics,
        suspicious: list[SuspiciousIndicator],
    ) -> list[SecurityRecommendation]:
        recs: list[SecurityRecommendation] = []
        if login_metrics.failure_rate > 0.3 and login_metrics.total >= 5:
            recs.append(SecurityRecommendation(
                priority="high",
                title="Yuqori login failure rate",
                description=f"Login failure rate {login_metrics.failure_rate:.0%} — IP blocking yoki CAPTCHA tavsiya etiladi",
            ))
        if session_metrics.stale > 3:
            recs.append(SecurityRecommendation(
                priority="medium",
                title="Stale sessionlarni tozalang",
                description=f"{session_metrics.stale} ta session 24+ soat harakatsiz",
            ))
        if session_metrics.expiring_soon > 5:
            recs.append(SecurityRecommendation(
                priority="low",
                title="Tez tugaydigan sessionlar",
                description=f"{session_metrics.expiring_soon} ta session 2 soat ichida tugaydi",
            ))
        high_alerts = [s for s in suspicious if s.severity == "high"]
        if high_alerts:
            recs.append(SecurityRecommendation(
                priority="high",
                title="Shubhali faollik aniqlandi",
                description=f"{len(high_alerts)} ta yuqori darajali ogohlantirish — tezkor tekshirish kerak",
            ))
        if denied_metrics.total_denied > 20:
            recs.append(SecurityRecommendation(
                priority="medium",
                title="Ko'p permission denied",
                description="RBAC role assignment tekshiring — foydalanuvchilarga kerakli ruxsatlar berilganmi?",
            ))
        if not recs:
            recs.append(SecurityRecommendation(
                priority="low",
                title="Xavfsizlik holati yaxshi",
                description="Hozircha shubhali faollik aniqlanmadi",
            ))
        return recs

    @staticmethod
    def build_security_dashboard(
        login_attempts: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        audit_entries: list[dict[str, Any]],
        period_hours: int = 24,
        now: datetime | None = None,
    ) -> SecurityDashboard:
        check_time = now or datetime.now(timezone.utc)
        login_m = AdminSecurityAuditService.get_login_attempt_metrics(login_attempts)
        session_m = AdminSecurityAuditService.get_session_metrics(sessions, now=check_time)
        denied_m = AdminSecurityAuditService.get_permission_denied_metrics(audit_entries)
        sensitive_m = AdminSecurityAuditService.get_sensitive_action_metrics(audit_entries)
        suspicious = AdminSecurityAuditService.detect_suspicious_activity(
            login_m, session_m, denied_m, sensitive_m, sessions,
        )
        recs = AdminSecurityAuditService.build_security_recommendations(
            login_m, session_m, denied_m, suspicious,
        )
        return SecurityDashboard(
            login_metrics=login_m,
            session_metrics=session_m,
            denied_metrics=denied_m,
            sensitive_metrics=sensitive_m,
            suspicious=suspicious,
            recommendations=recs,
            generated_at=check_time.isoformat(),
            period_hours=period_hours,
        )

    @staticmethod
    def get_recent_audit_events(
        audit_entries: list[dict[str, Any]],
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sorted_entries = sorted(
            audit_entries,
            key=lambda e: e.get("created_at", ""),
            reverse=True,
        )[:limit]
        return [AdminSecurityAuditService.sanitize_audit_entry(e) for e in sorted_entries]

    @staticmethod
    def sanitize_ip(ip: str) -> str:
        if not ip:
            return ""
        return ip[:45]

    @staticmethod
    def sanitize_admin_id(admin_id: str) -> str:
        if not admin_id:
            return ""
        return admin_id[:100]

    @staticmethod
    def sanitize_user_agent(user_agent: str) -> str:
        if not user_agent:
            return ""
        ua = user_agent[:200]
        ua = _TOKEN_RE.sub("[REDACTED]", ua)
        ua = _BOT_TOKEN_RE.sub("[REDACTED]", ua)
        return ua

    @staticmethod
    def sanitize_audit_entry(entry: dict[str, Any]) -> dict[str, Any]:
        safe = dict(entry)
        safe.pop("session_id_hash", None)
        if safe.get("metadata_json"):
            safe["metadata_json"] = AdminSecurityAuditService.sanitize_audit_metadata(
                safe["metadata_json"],
            )
        if safe.get("reason"):
            safe["reason"] = _TOKEN_RE.sub("[REDACTED]", safe["reason"])
            safe["reason"] = _BOT_TOKEN_RE.sub("[REDACTED]", safe["reason"])
        if safe.get("user_agent"):
            safe["user_agent"] = AdminSecurityAuditService.sanitize_user_agent(safe["user_agent"])
        return safe

    @staticmethod
    def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
        if metadata is None:
            return None
        safe: dict[str, Any] = {}
        for key, val in metadata.items():
            if isinstance(val, str):
                val = _TOKEN_RE.sub("[REDACTED]", val)
                val = _BOT_TOKEN_RE.sub("[REDACTED]", val)
            safe[key] = val
        return safe


def _parse_dt(val: Any) -> datetime | None:
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, str) and val:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def _extract_permission_from_reason(reason: str) -> str:
    if "does not have" in reason:
        parts = reason.split("does not have")
        if len(parts) == 2:
            return parts[1].strip()
    return ""
