"""Frozen dataclasses for admin security audit dashboard schemas."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdminSecurityDashboardSchema:
    login_metrics: dict[str, Any] = field(default_factory=dict)
    session_metrics: dict[str, Any] = field(default_factory=dict)
    denied_metrics: dict[str, Any] = field(default_factory=dict)
    sensitive_metrics: dict[str, Any] = field(default_factory=dict)
    suspicious: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""
    period_hours: int = 24


@dataclass(frozen=True)
class RecentSecurityEvent:
    action: str = ""
    actor_admin_id: str = ""
    actor_role: str = ""
    target_type: str = ""
    target_id: str = ""
    status: str = ""
    reason: str = ""
    created_at: str = ""
