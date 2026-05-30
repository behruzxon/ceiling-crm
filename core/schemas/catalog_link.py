"""Frozen dataclasses for the design-specific catalog deep-link resolver."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CatalogLink:
    key: str = ""
    title: str = ""
    url: str = ""


@dataclass(frozen=True)
class CatalogLinkResult:
    matched: bool = False
    needs_confirmation: bool = False
    confidence: int = 0
    link: CatalogLink | None = None
    candidates: tuple[CatalogLink, ...] = field(default_factory=tuple)
    fallback_link: CatalogLink | None = None
    intro_text: str = ""
    confirmation_question: str = ""
    source_text_preview: str = ""
    reason: str = ""
