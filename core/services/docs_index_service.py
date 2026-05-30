"""
core.services.docs_index_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Read-only scanner that turns the ``docs/AI_AGENT_SYSTEM/*.md`` tree
into a frozen :class:`DocsIndex` for the admin Help page.

Hard guarantees:

* Only top-level ``*.md`` files inside the supplied directory are
  scanned. Sub-directories and dotfiles are skipped.
* Files are read only with explicit ``utf-8`` decoding and small
  byte caps (the summary uses the first 8 KiB only).
* Symbolic links pointing outside ``docs_dir`` are dropped (path
  traversal defence).
* Sensitive markers (``BOT_TOKEN``, ``OPENAI``, ``DATABASE_URL``,
  ``postgres://``, ``redis://``, ``Bearer``, ``sk-…``) are redacted
  from titles and summaries before they reach the template, and the
  affected entry is flagged ``is_safe=False`` with a warning.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from core.schemas.docs_index import (
    DocsIndex,
    DocsIndexEntry,
    DocsIndexGroup,
)

# ── Constants ──────────────────────────────────────────────────────────

_MAX_SUMMARY_CHARS = 180
_MAX_READ_BYTES = 8_192

_GROUP_DEFINITIONS: tuple[dict, ...] = (
    {
        "area": "foundation",
        "title": "Foundation / Early docs",
        "description": "Birinchi bosqich loyiha hujjatlari.",
        "range": (1, 49),
    },
    {
        "area": "ai_agent_stage1_prep",
        "title": "AI Agent / Stage 1 prep",
        "description": "Agent va Stage 1 ga tayyorgarlik.",
        "range": (50, 89),
    },
    {
        "area": "crm_web_hardening",
        "title": "CRM / Web / AI hardening",
        "description": "CRM va web qatlamining mustahkamlash hujjatlari.",
        "range": (90, 119),
    },
    {
        "area": "deployment_readiness",
        "title": "Deployment / Production readiness",
        "description": "Production deploy va VPS tayyorgarligi.",
        "range": (120, 129),
    },
    {
        "area": "audit_local_polish",
        "title": "Audit / Blocker fixes / Local polish",
        "description": "Audit, blocker yopishi va mahalliy yaxshilanishlar.",
        "range": (130, 139),
    },
    {
        "area": "local_feature_docs",
        "title": "Local feature docs",
        "description": "Mahalliy F-feature pack hujjatlari.",
        "range": (140, 9999),
    },
)

_OTHER_GROUP = {
    "area": "other",
    "title": "Other",
    "description": "Raqamlanmagan yoki tashqi hujjatlar.",
    "range": None,
}

# Sensitive substring markers and regex patterns. A match in the raw
# title or summary triggers ``is_safe=False`` and full redaction of
# that field. We never let the original bytes through.
_SENSITIVE_MARKER_STRINGS: tuple[str, ...] = (
    "BOT_TOKEN",
    "OPENAI",
    "DATABASE_URL",
)

_SENSITIVE_MARKER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"postgres(?:ql)?://[^\s\"']+"),
    re.compile(r"redis://[^\s\"']+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"),
)


_FILENAME_NUMBER_RE = re.compile(r"^(\d{1,4})[_-]")
_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


# ── Public API ─────────────────────────────────────────────────────────


def build_docs_index(docs_dir: Path | str | None) -> DocsIndex:
    """Build a frozen :class:`DocsIndex` from on-disk markdown files."""
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    if docs_dir is None:
        return DocsIndex(
            generated_at=generated_at,
            empty_reason="Docs directory not provided.",
        )

    root = Path(docs_dir)
    if not root.is_dir():
        return DocsIndex(
            generated_at=generated_at,
            empty_reason=f"Docs directory not found: {root}",
        )

    root_resolved = root.resolve()
    entries: list[DocsIndexEntry] = []

    for path in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        if path.suffix.lower() != ".md":
            continue
        if path.name.startswith("."):
            continue
        if not _within(path, root_resolved):
            continue

        entry = _read_entry(path, root_resolved)
        entries.append(entry)

    entries.sort(key=lambda e: (e.doc_id if e.doc_id else 10_000, e.filename))

    groups = _group_entries(entries)
    return DocsIndex(
        groups=groups,
        total_docs=len(entries),
        generated_at=generated_at,
        empty_reason="" if entries else "Hech qanday markdown hujjat topilmadi.",
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _within(path: Path, root_resolved: Path) -> bool:
    try:
        path.resolve().relative_to(root_resolved)
    except (OSError, ValueError):
        return False
    return True


def _read_entry(path: Path, root_resolved: Path) -> DocsIndexEntry:
    doc_id = _extract_doc_id(path.name)
    area = _area_for_id(doc_id)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    try:
        with path.open("rb") as f:
            raw_bytes = f.read(_MAX_READ_BYTES)
        text = raw_bytes.decode("utf-8", errors="replace")
    except OSError:
        return DocsIndexEntry(
            doc_id=doc_id,
            filename=path.name,
            title=path.stem,
            summary="",
            area=area,
            relative_path=path.name,
            size_bytes=size,
            is_safe=True,
            warning="",
        )

    title = _extract_title(text) or path.stem
    summary = _extract_summary(text)

    safe_title, title_redacted = _redact(title)
    safe_summary, summary_redacted = _redact(summary)

    is_safe = not (title_redacted or summary_redacted)
    warning = "Sensitive marker redacted" if not is_safe else ""

    return DocsIndexEntry(
        doc_id=doc_id,
        filename=path.name,
        title=safe_title or path.stem,
        summary=safe_summary,
        area=area,
        relative_path=path.name,
        size_bytes=size,
        is_safe=is_safe,
        warning=warning,
    )


def _extract_doc_id(filename: str) -> int:
    match = _FILENAME_NUMBER_RE.match(filename)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


def _area_for_id(doc_id: int) -> str:
    if doc_id <= 0:
        return _OTHER_GROUP["area"]
    for group in _GROUP_DEFINITIONS:
        low, high = group["range"]
        if low <= doc_id <= high:
            return group["area"]
    return _OTHER_GROUP["area"]


def _extract_title(text: str) -> str:
    match = _H1_RE.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def _extract_summary(text: str) -> str:
    # Strip the first H1 line so the summary starts at the first
    # paragraph that follows. Front-matter and block-quote prologues
    # are skipped to keep the summary informative.
    lines = text.splitlines()
    body: list[str] = []
    seen_h1 = False
    for line in lines:
        stripped = line.strip()
        if not seen_h1 and stripped.startswith("#"):
            seen_h1 = True
            continue
        if not seen_h1:
            continue
        if not stripped:
            if body:
                break
            continue
        if stripped.startswith(">"):
            continue
        if stripped.startswith("#"):
            continue
        body.append(stripped)
        if sum(len(p) + 1 for p in body) >= _MAX_SUMMARY_CHARS * 2:
            break
    summary = " ".join(body).strip()
    if not summary and lines:
        # Fallback: take the first non-empty, non-blockquote line.
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(">") or stripped.startswith("#"):
                continue
            summary = stripped
            break
    if len(summary) > _MAX_SUMMARY_CHARS:
        summary = summary[: _MAX_SUMMARY_CHARS - 1].rstrip() + "…"
    return summary


def _redact(text: str) -> tuple[str, bool]:
    if not text:
        return "", False
    redacted = False
    cleaned = text
    for marker in _SENSITIVE_MARKER_STRINGS:
        if marker.lower() in cleaned.lower():
            cleaned = re.sub(re.escape(marker), "[REDACTED]", cleaned, flags=re.I)
            redacted = True
    for pattern in _SENSITIVE_MARKER_PATTERNS:
        if pattern.search(cleaned):
            cleaned = pattern.sub("[REDACTED]", cleaned)
            redacted = True
    return cleaned, redacted


def _group_entries(entries: list[DocsIndexEntry]) -> tuple[DocsIndexGroup, ...]:
    by_area: dict[str, list[DocsIndexEntry]] = {}
    for entry in entries:
        by_area.setdefault(entry.area, []).append(entry)

    groups: list[DocsIndexGroup] = []
    for spec in _GROUP_DEFINITIONS:
        area = spec["area"]
        members = by_area.pop(area, [])
        if not members:
            continue
        groups.append(
            DocsIndexGroup(
                area=area,
                title=spec["title"],
                description=spec["description"],
                entries=tuple(members),
            )
        )

    # Anything left over (e.g. unnumbered docs) goes into "Other".
    other_members: list[DocsIndexEntry] = []
    for members in by_area.values():
        other_members.extend(members)
    if other_members:
        groups.append(
            DocsIndexGroup(
                area=_OTHER_GROUP["area"],
                title=_OTHER_GROUP["title"],
                description=_OTHER_GROUP["description"],
                entries=tuple(other_members),
            )
        )

    return tuple(groups)


__all__ = ["build_docs_index"]
