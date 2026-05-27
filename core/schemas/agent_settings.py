"""Frozen dataclasses for agent settings mutation API."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSettingValue:
    key: str
    value: object
    source: str = "default"
    risk_level: str = "low"
    value_type: str = "bool"


@dataclass(frozen=True)
class AgentSettingsValidationResult:
    allowed: bool
    risk_level: str = "low"
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    confirmation_token: str | None = None
