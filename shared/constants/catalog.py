"""Catalog section definitions — single source of truth.

Each CatalogSection maps a short key to a display title and the Telegram
group URL where that ceiling style is showcased.  The order of CATALOG
determines the display order in the inline keyboard.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CatalogSection:
    key: str
    title: str
    group_url: str
    short_description: str = field(default="")


CATALOG: tuple[CatalogSection, ...] = (
    CatalogSection("gulli",         "Gulli",                  "https://t.me/vashpotolokuz/2"),
    CatalogSection("odnotonniy",    "Odnotonniy",             "https://t.me/vashpotolokuz/3661"),
    CatalogSection("mramor",        "Mramor",                 "https://t.me/vashpotolokuz/879"),
    CatalogSection("qora_naqsh_uf", "Qora naqsh (UF pechat)", "https://t.me/vashpotolokuz/1666"),
    CatalogSection("hi_tech",       "Hi-tech",                "https://t.me/vashpotolokuz/2668"),
    CatalogSection("kosmos",        "Kosmos",                 "https://t.me/vashpotolokuz/3063"),
    CatalogSection("osmon",         "Osmon",                  "https://t.me/vashpotolokuz/3343"),
    CatalogSection("oshxona",       "Oshxona",                "https://t.me/vashpotolokuz/3767"),
    CatalogSection("naqsh_ramka",   "Naqsh ramka",            "https://t.me/vashpotolokuz/1979"),
    CatalogSection("naqsh_oq",      "Naqsh oq",               "https://t.me/vashpotolokuz/1419"),
)

# O(1) lookup by key — built once at import time.
CATALOG_BY_KEY: dict[str, CatalogSection] = {s.key: s for s in CATALOG}
