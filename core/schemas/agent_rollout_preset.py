"""Frozen dataclasses for agent rollout presets."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentRolloutPresetDiff:
    key: str
    current_value: object
    target_value: object
    risk_level: str = "low"


@dataclass(frozen=True)
class AgentRolloutPresetDefinition:
    name: str
    label: str
    description: str
    risk_level: str
    settings: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentRolloutPresetPreviewResponse:
    preset: str
    allowed: bool
    risk_level: str
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diff: list[AgentRolloutPresetDiff] = field(default_factory=list)
    requires_confirmation: bool = False
    confirmation_token: str | None = None
