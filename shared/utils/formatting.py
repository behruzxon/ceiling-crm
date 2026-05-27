"""Text formatting utilities for Telegram HTML messages."""

from __future__ import annotations

from decimal import Decimal


def fmt_currency(amount: Decimal, currency: str = "UZS") -> str:
    """Format currency for Telegram display. e.g.: 1,250,000 UZS"""
    formatted = f"{int(amount):,}".replace(",", " ")
    return f"{formatted} {currency}"


def fmt_area(area: Decimal) -> str:
    """Format area in sqm. e.g.: 24.5 m²"""
    return f"{area:.1f} m²"


def bold(text: str) -> str:
    return f"<b>{text}</b>"


def italic(text: str) -> str:
    return f"<i>{text}</i>"


def code(text: str) -> str:
    return f"<code>{text}</code>"


def link(text: str, url: str) -> str:
    return f'<a href="{url}">{text}</a>'
