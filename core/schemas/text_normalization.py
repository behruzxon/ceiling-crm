"""Frozen dataclass for text normalization results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class NormalizedText:
    original: str
    normalized: str
    latin: str
    tokens: list[str] = field(default_factory=list)
    ngrams: list[str] = field(default_factory=list)
    detected_scripts: list[str] = field(default_factory=list)
    detected_languages: list[str] = field(default_factory=list)
    typo_corrections: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
