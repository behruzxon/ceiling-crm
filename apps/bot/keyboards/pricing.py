"""Reply and inline keyboards used in the pricing calculator FSM flow."""
from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


@dataclass(frozen=True)
class DesignOption:
    """One ceiling design variant with its per-m² price in UZS."""

    label: str
    price_per_sqm: int


# Single source of truth for all available ceiling designs.
# Key is used as the callback_data payload: "design:<key>".
DESIGN_BY_KEY: dict[str, DesignOption] = {
    "gulli":         DesignOption("Gulli",                  120_000),
    "odnotonniy":    DesignOption("Odnotonniy",              80_000),
    "mramor":        DesignOption("Mramor",                 120_000),
    "qora_naqsh_uf": DesignOption("Qora naqsh (UF pechat)", 140_000),
    "hi_tech":       DesignOption("Hi-tech",                130_000),
    "kosmos_osmon":  DesignOption("Kosmos / osmon",         120_000),
}


def design_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard listing all ceiling design variants with their prices."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{opt.label} — {opt.price_per_sqm:,} UZS/m²",
                    callback_data=f"design:{key}",
                )
            ]
            for key, opt in DESIGN_BY_KEY.items()
        ]
    )


def after_quote_keyboard() -> ReplyKeyboardMarkup:
    """
    Shown immediately after the price breakdown is displayed.
    Gives the user three choices:
      - Place a full order (hands off to lead-capture FSM)
      - Speak to an operator
      - Recalculate with different dimensions
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📦 Buyurtma berish"),
                KeyboardButton(text="📞 Operator"),
            ],
            [KeyboardButton(text="🔄 Qayta hisoblash")],
        ],
        resize_keyboard=True,
    )
