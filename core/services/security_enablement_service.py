"""
core.services.security_enablement_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Security staged enablement preflight checks. Pure functions.
No DB I/O, no mutations, no secrets printed.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

_STAGES = ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7")

_STAGE_DESCRIPTIONS = {
    "S0": "Legacy Safe Mode — all security features OFF",
    "S1": "Env RBAC Observe — permission behavior monitoring",
    "S2": "DB RBAC Observe — database roles with env fallback",
    "S3": "Session Auth Staging — login/session testing",
    "S4": "CSRF Staging — form/API mutation protection",
    "S5": "Security Actions Staging — revoke/disable/IP watch",
    "S6": "IP Watch Mode — advisory only, no enforcement",
    "S7": "IP Enforcement Limited — actual block rules active",
}

_STAGE_FLAGS: dict[str, dict[str, bool]] = {
    "S0": {
        "admin_rbac_enabled": False, "admin_db_rbac_enabled": False,
        "admin_session_auth_enabled": False, "admin_csrf_enabled": False,
        "admin_security_actions_enabled": False, "admin_ip_rules_enabled": False,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S1": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": False,
        "admin_session_auth_enabled": False, "admin_csrf_enabled": False,
        "admin_security_actions_enabled": False, "admin_ip_rules_enabled": False,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S2": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": True,
        "admin_db_rbac_fallback_to_env": True,
        "admin_session_auth_enabled": False, "admin_csrf_enabled": False,
        "admin_security_actions_enabled": False, "admin_ip_rules_enabled": False,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S3": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": True,
        "admin_db_rbac_fallback_to_env": True,
        "admin_session_auth_enabled": True, "admin_csrf_enabled": False,
        "admin_security_actions_enabled": False, "admin_ip_rules_enabled": False,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S4": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": True,
        "admin_session_auth_enabled": True, "admin_csrf_enabled": True,
        "admin_security_actions_enabled": False, "admin_ip_rules_enabled": False,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S5": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": True,
        "admin_session_auth_enabled": True, "admin_csrf_enabled": True,
        "admin_security_actions_enabled": True, "admin_ip_rules_enabled": True,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S6": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": True,
        "admin_session_auth_enabled": True, "admin_csrf_enabled": True,
        "admin_security_actions_enabled": True, "admin_ip_rules_enabled": True,
        "admin_ip_block_enforcement_enabled": False,
    },
    "S7": {
        "admin_rbac_enabled": True, "admin_db_rbac_enabled": True,
        "admin_session_auth_enabled": True, "admin_csrf_enabled": True,
        "admin_security_actions_enabled": True, "admin_ip_rules_enabled": True,
        "admin_ip_block_enforcement_enabled": True,
    },
}


@dataclass(frozen=True)
class PreflightCheck:
    name: str = ""
    status: str = "green"
    message: str = ""
    stage: str = ""


@dataclass(frozen=True)
class PreflightReport:
    stage: str = "S0"
    stage_description: str = ""
    checks: list[PreflightCheck] = field(default_factory=list)
    overall: str = "green"
    can_proceed: bool = True
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RollbackCard:
    from_stage: str = ""
    to_stage: str = ""
    steps: list[str] = field(default_factory=list)
    flags_to_set: dict[str, bool] = field(default_factory=dict)


class SecurityEnablementService:
    """Security staged enablement preflight and rollback."""

    @staticmethod
    def get_stages() -> tuple[str, ...]:
        return _STAGES

    @staticmethod
    def get_stage_description(stage: str) -> str:
        return _STAGE_DESCRIPTIONS.get(stage, "Unknown stage")

    @staticmethod
    def get_stage_flags(stage: str) -> dict[str, bool]:
        return dict(_STAGE_FLAGS.get(stage, _STAGE_FLAGS["S0"]))

    @staticmethod
    def detect_current_stage(settings: dict[str, Any]) -> str:
        for stage in reversed(_STAGES):
            flags = _STAGE_FLAGS[stage]
            match = True
            for key, val in flags.items():
                if settings.get(key) != val:
                    match = False
                    break
            if match:
                return stage
        return "S0"

    @staticmethod
    def run_preflight(
        settings: dict[str, Any],
        target_stage: str = "",
        has_db_owner: bool = False,
        has_secret_key: bool = False,
    ) -> PreflightReport:
        if not target_stage:
            target_stage = SecurityEnablementService.detect_current_stage(settings)
        checks: list[PreflightCheck] = []
        blockers: list[str] = []
        warnings: list[str] = []

        # Check 1: Session auth + secret key
        if settings.get("admin_session_auth_enabled"):
            if not has_secret_key:
                checks.append(PreflightCheck("secret_key", "red", "Session auth enabled but no APP_SECRET_KEY", target_stage))
                blockers.append("Session auth requires APP_SECRET_KEY")
            else:
                checks.append(PreflightCheck("secret_key", "green", "APP_SECRET_KEY present", target_stage))

        # Check 2: DB RBAC + owner
        if settings.get("admin_db_rbac_enabled"):
            fallback = settings.get("admin_db_rbac_fallback_to_env", True)
            if not has_db_owner and not fallback:
                checks.append(PreflightCheck("db_rbac_owner", "red", "DB RBAC enabled, no owner, fallback disabled — LOCKOUT RISK", target_stage))
                blockers.append("DB RBAC without owner and without fallback = lockout")
            elif not has_db_owner and fallback:
                checks.append(PreflightCheck("db_rbac_owner", "yellow", "DB RBAC enabled, no owner in DB — env fallback active", target_stage))
                warnings.append("No owner in admin_users DB — relying on env fallback")
            else:
                checks.append(PreflightCheck("db_rbac_owner", "green", "DB RBAC enabled with owner in DB", target_stage))

        # Check 3: CSRF + session auth
        if settings.get("admin_csrf_enabled") and not settings.get("admin_session_auth_enabled"):
            checks.append(PreflightCheck("csrf_session", "red", "CSRF enabled but session auth disabled — CSRF useless", target_stage))
            blockers.append("CSRF requires session auth to be enabled first")
        elif settings.get("admin_csrf_enabled"):
            checks.append(PreflightCheck("csrf_session", "green", "CSRF enabled with session auth", target_stage))

        # Check 4: Security actions + audit
        if settings.get("admin_security_actions_enabled"):
            if not settings.get("admin_security_action_audit_enabled", True):
                checks.append(PreflightCheck("actions_audit", "yellow", "Security actions enabled without audit logging", target_stage))
                warnings.append("Security actions without audit = no accountability trail")
            else:
                checks.append(PreflightCheck("actions_audit", "green", "Security actions with audit enabled", target_stage))

        # Check 5: IP enforcement + fallback
        if settings.get("admin_ip_block_enforcement_enabled"):
            if not settings.get("admin_db_rbac_fallback_to_env", True):
                checks.append(PreflightCheck("ip_enforcement_fallback", "red", "IP enforcement ON without env fallback — lockout risk", target_stage))
                blockers.append("IP enforcement without env fallback = potential lockout")
            else:
                checks.append(PreflightCheck("ip_enforcement_fallback", "green", "IP enforcement ON with env fallback", target_stage))

        # Check 6: Secure cookie on localhost
        if settings.get("admin_session_auth_enabled") and settings.get("admin_session_secure_cookie", True):
            app_env = settings.get("app_env", "development")
            if app_env == "development":
                checks.append(PreflightCheck("secure_cookie_dev", "yellow", "Secure cookie=true on development — may fail on HTTP", target_stage))
                warnings.append("Secure cookie on dev mode may block cookie setting over HTTP")

        # Check 7: Login max attempts
        max_attempts = settings.get("admin_login_max_attempts", 5)
        if max_attempts < 3:
            checks.append(PreflightCheck("login_max_attempts", "yellow", f"Login max attempts={max_attempts} — easy lockout", target_stage))
            warnings.append(f"Login max attempts={max_attempts} is very low")

        # Check 8: All defaults = safe mode
        if not any(settings.get(k) for k in [
            "admin_rbac_enabled", "admin_db_rbac_enabled",
            "admin_session_auth_enabled", "admin_csrf_enabled",
            "admin_security_actions_enabled", "admin_ip_block_enforcement_enabled",
        ]):
            checks.append(PreflightCheck("safe_mode", "green", "All security features OFF — safe legacy mode", target_stage))

        overall = "red" if blockers else ("yellow" if warnings else "green")
        return PreflightReport(
            stage=target_stage,
            stage_description=SecurityEnablementService.get_stage_description(target_stage),
            checks=checks,
            overall=overall,
            can_proceed=len(blockers) == 0,
            blockers=blockers,
            warnings=warnings,
        )

    @staticmethod
    def build_rollback_card(from_stage: str, to_stage: str = "") -> RollbackCard:
        if not to_stage:
            idx = _STAGES.index(from_stage) if from_stage in _STAGES else 0
            to_stage = _STAGES[max(0, idx - 1)]
        target_flags = _STAGE_FLAGS.get(to_stage, _STAGE_FLAGS["S0"])
        steps: list[str] = []
        current_flags = _STAGE_FLAGS.get(from_stage, {})
        for key, val in current_flags.items():
            target_val = target_flags.get(key, False)
            if val != target_val:
                env_key = key.upper()
                steps.append(f"Set {env_key}={'true' if target_val else 'false'}")
        steps.append("Restart application")
        steps.append("Verify dashboard access")
        steps.append("Check admin login works")
        return RollbackCard(
            from_stage=from_stage,
            to_stage=to_stage,
            steps=steps,
            flags_to_set=dict(target_flags),
        )

    @staticmethod
    def build_config_matrix() -> list[dict[str, Any]]:
        matrix: list[dict[str, Any]] = []
        for stage in _STAGES:
            flags = _STAGE_FLAGS[stage]
            matrix.append({
                "stage": stage,
                "description": _STAGE_DESCRIPTIONS[stage],
                "flags": flags,
            })
        return matrix

    @staticmethod
    def get_next_stage(current: str) -> str | None:
        if current not in _STAGES:
            return "S0"
        idx = _STAGES.index(current)
        if idx < len(_STAGES) - 1:
            return _STAGES[idx + 1]
        return None

    @staticmethod
    def get_previous_stage(current: str) -> str | None:
        if current not in _STAGES:
            return None
        idx = _STAGES.index(current)
        if idx > 0:
            return _STAGES[idx - 1]
        return None
