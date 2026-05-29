"""Frozen dataclasses for the CRM docs index / admin help page.

The index is built read-only from on-disk markdown files; nothing in
it carries raw secrets. Each entry has its own ``is_safe`` flag plus
an optional ``warning`` so the template can flag a doc whose summary
contained a sensitive marker before redaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DocsIndexEntry:
    doc_id: int = 0
    filename: str = ""
    title: str = ""
    summary: str = ""
    area: str = "other"
    relative_path: str = ""
    size_bytes: int = 0
    is_safe: bool = True
    warning: str = ""


@dataclass(frozen=True)
class DocsIndexGroup:
    area: str = "other"
    title: str = "Other"
    description: str = ""
    entries: tuple[DocsIndexEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DocsIndex:
    groups: tuple[DocsIndexGroup, ...] = field(default_factory=tuple)
    total_docs: int = 0
    generated_at: str = ""
    empty_reason: str = ""
