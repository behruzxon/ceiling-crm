"""
core.services.catalog_link_resolver_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pure resolver that maps free-form Uzbek customer text to one of the
existing ``CATALOG_BY_KEY`` entries in :mod:`shared.constants.catalog`.

Behaviour:

* If the text mentions a known design / category alias → return the
  matching ``CatalogLink`` with the existing Telegram folder URL.
* If no alias matches → return ``matched=False`` and a fallback
  ``CatalogLink`` pointing at the generic full catalog
  (``https://t.me/vashpotolokuz``).
* If a design is recognised but its URL is empty (placeholder) →
  return ``matched=True`` with ``link.url == ""`` and the fallback so
  the caller can switch to the generic message.

**No** URLs are invented here. Everything comes from
``shared.constants.catalog.CATALOG``.
"""

from __future__ import annotations

import re

from core.schemas.catalog_link import CatalogLink, CatalogLinkResult
from shared.constants.catalog import CATALOG_BY_KEY

# Generic full-catalog URL (mirrors the existing _catalog_link_kb).
_GENERIC_URL = "https://t.me/vashpotolokuz"
_GENERIC_TITLE = "📂 To'liq katalog"


# Aliases → key in CATALOG_BY_KEY. Longest aliases first so multi-word
# matches ("naqsh oq") win before single-word ones ("naqsh ramka").
_ALIAS_TO_KEY: tuple[tuple[str, str], ...] = (
    # ── 2-word phrases first ──────────────────────────────────────────
    ("naqsh ramka", "naqsh_ramka"),
    ("naqsh oq", "naqsh_oq"),
    ("qora naqsh", "qora_naqsh_uf"),
    ("qora uf", "qora_naqsh_uf"),
    ("uf pechat", "qora_naqsh_uf"),
    ("hi tech", "hi_tech"),
    ("hi-tech", "hi_tech"),
    # ── single-word aliases ───────────────────────────────────────────
    ("gullili", "gulli"),
    ("gulli", "gulli"),
    ("guli", "gulli"),
    ("odnotonniy", "odnotonniy"),
    ("odnoton", "odnotonniy"),
    ("adnatonniy", "odnotonniy"),
    ("adnatoni", "odnotonniy"),
    ("oddiy", "odnotonniy"),
    ("matoviy", "odnotonniy"),
    ("matt", "odnotonniy"),
    ("satin", "odnotonniy"),
    ("mramor", "mramor"),
    ("marble", "mramor"),
    ("hitech", "hi_tech"),
    ("led", "hi_tech"),
    ("shadow", "hi_tech"),
    ("kosmos", "kosmos"),
    ("kuxnya", "oshxona"),
    ("kitchen", "oshxona"),
    ("oshxona", "oshxona"),
    ("pechat", "qora_naqsh_uf"),
    ("osmon", "osmon"),
    # Bare "gul" is the most aggressive — keep it last so "gullili"
    # / "guli" win first when the text contains them.
    ("gul", "gulli"),
    ("naqsh", "naqsh_ramka"),
)

_WORD_BOUNDARY = re.compile(r"[a-z0-9'']+")


def _normalize(text: str) -> str:
    if not text:
        return ""
    return text.lower().replace("’", "'").strip()


def resolve_catalog_link(text: str | None) -> CatalogLinkResult:
    """Return the best-matching design catalog for ``text``.

    Pure: no I/O. Safe to call from any layer.
    """
    fallback = _make_fallback()

    normalised = _normalize(text or "")
    if not normalised:
        return CatalogLinkResult(
            matched=False,
            link=None,
            fallback_link=fallback,
            intro_text="Mana to'liq katalogimiz 👇",
            reason="empty_text",
        )

    matched_key: str | None = None
    for alias, key in _ALIAS_TO_KEY:
        if alias in normalised:
            matched_key = key
            break

    if matched_key is None:
        return CatalogLinkResult(
            matched=False,
            link=None,
            fallback_link=fallback,
            intro_text="Mana to'liq katalogimiz 👇",
            reason="no_design_alias",
        )

    section = CATALOG_BY_KEY.get(matched_key)
    if section is None:
        # Defence-in-depth: alias points to a key that's not in the
        # canonical CATALOG. Fall back rather than crash.
        return CatalogLinkResult(
            matched=False,
            link=None,
            fallback_link=fallback,
            intro_text="Mana to'liq katalogimiz 👇",
            reason=f"missing_section:{matched_key}",
        )

    if not section.group_url:
        return CatalogLinkResult(
            matched=True,
            link=CatalogLink(key=section.key, title=section.title, url=""),
            fallback_link=fallback,
            intro_text=(
                f"Bu bo'lim ({section.title}) uchun alohida link hali "
                "sozlanmagan. Mana to'liq katalogimiz 👇"
            ),
            reason="link_missing",
        )

    return CatalogLinkResult(
        matched=True,
        link=CatalogLink(key=section.key, title=section.title, url=section.group_url),
        fallback_link=fallback,
        intro_text=f"Albatta, mana {section.title} katalogimiz 👇",
        reason="ok",
    )


def _make_fallback() -> CatalogLink:
    return CatalogLink(key="all", title=_GENERIC_TITLE, url=_GENERIC_URL)
