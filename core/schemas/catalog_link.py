"""Frozen dataclasses for the design-specific catalog deep-link resolver."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogLink:
    key: str = ""
    title: str = ""
    url: str = ""


@dataclass(frozen=True)
class CatalogLinkResult:
    matched: bool = False
    link: CatalogLink | None = None
    fallback_link: CatalogLink | None = None
    intro_text: str = ""
    reason: str = ""
