"""
shared.constants.packages
~~~~~~~~~~~~~~~~~~~~~~~~~~
Tenant-agnostic package catalogue for stretch ceiling products.

Extracted from apps.bot.handlers.private.packages so the same data
can be used by the web API without depending on aiogram.

Usage
-----
  from shared.constants.packages import PACKAGES, PACKAGES_LIST_TEXT

  pkg = PACKAGES.get("premium")
  if pkg:
      print(pkg.name, pkg.price_per_m2)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PackageSpec:
    """Immutable specification for a single ready-made package."""

    key: str
    name: str
    description: str
    price_per_m2: int
    score_delta: int
    status: str


PACKAGES: dict[str, PackageSpec] = {
    "standard": PackageSpec(
        key="standard",
        name="🥉 Standard",
        description=(
            "🥉 <b>STANDARD — Eng arzon va tez variant</b>\n\n"
            "• Oddiy va ishonchli natijnoy patalok\n"
            "• ⚡ Eng tez o'rnatish\n"
            "• 💸 Har qanday boshqa potolok turidan arzon\n"
            "• 🎨 10+ rang tanlov\n"
            "• 🛡 10 yil kafolat\n\n"
            "💰 Narx: <b>80 000 UZS/m²</b>\n\n"
            "🎯 <i>Ijara uylari va byudjet variant uchun ideal</i>"
        ),
        price_per_m2=80_000,
        score_delta=5,
        status="warm",
    ),
    "premium": PackageSpec(
        key="premium",
        name="🥈 Premium ⭐",
        description=(
            "🥈 <b>PREMIUM ⭐ Eng ko'p tanlanadi</b>\n\n"
            "• 🌸 Gulli dizayn variantlar\n"
            "• 🧩 Hi-tech zamonaviy uslub\n"
            "• 🪨 Mramor (marmar) effektli naqshlar\n"
            "• 🎨 10 000+ dizayn va faktura\n"
            "• 💡 LED bilan uyg'un dizayn\n"
            "• 🛡 10 yil kafolat\n\n"
            "💰 Narx: <b>120 000 UZS/m²</b>"
        ),
        price_per_m2=120_000,
        score_delta=10,
        status="hot",
    ),
    "vip": PackageSpec(
        key="vip",
        name="🥇 VIP 👑",
        description=(
            "🥇 <b>VIP 👑 Eksklyuziv dizayn</b>\n\n"
            "• 🧩 Murakkab hi-tech dizaynlar\n"
            "• 💡 Spot chiroqlar integratsiyasi\n"
            "• ➖ Trek sistema\n"
            "• ✨ Svetavoy liniya\n"
            "• 🌈 RGB + ko'p darajali yoritish\n"
            "• 🏗 Ko'p bosqichli konstruktsiya\n"
            "• 🎨 Individual loyiha asosida dizayn\n"
            "• 📐 Bepul o'lchov + dizayn loyiha\n"
            "• 🛡 15 yil kafolat\n\n"
            "💰 Narx: <b>140 000 – 1 000 000 UZS/m²</b>"
        ),
        price_per_m2=140_000,
        score_delta=15,
        status="hot",
    ),
}

PACKAGE_KEYS: tuple[str, ...] = tuple(PACKAGES.keys())

PACKAGES_LIST_TEXT: str = (
    "📦 <b>Tayyor paketlar</b>\n\n"
    "Eng qulay paketni tanlang va operator tez orada bog'lanadi:\n\n"
    "🥉 <b>Standard</b> — 80 000 UZS/m²\n"
    "🥈 <b>Premium</b> ⭐ — 120 000 UZS/m²  <i>(eng ko'p tanlanadi)</i>\n"
    "🥇 <b>VIP</b> 👑 — 140 000 – 1 000 000 UZS/m²\n\n"
    "👇 Paketni tanlang:"
)
