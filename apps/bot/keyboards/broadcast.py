"""Inline keyboards for the admin broadcast FSM."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from shared.constants.enums import PipelineStage

# ── Segment chooser ───────────────────────────────────────────────────────────

def segment_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Barcha foydalanuvchilar", callback_data="bcast:seg:all"),
    )
    builder.row(
        InlineKeyboardButton(text="🔀 Bosqich bo'yicha", callback_data="bcast:seg:stage"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Admin guruhlar", callback_data="bcast:seg:groups"),
    )
    builder.row(
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bcast:cancel"),
    )
    return builder.as_markup()


# ── Pipeline stage chooser ────────────────────────────────────────────────────

_STAGE_LABELS: dict[str, str] = {
    PipelineStage.NEW.value:          "🆕 Yangi",
    PipelineStage.CONTACTED.value:    "📞 Bog'lanildi",
    PipelineStage.MEASUREMENT.value:  "📐 O'lchov",
    PipelineStage.QUOTE.value:        "💵 Narx taklifi",
    PipelineStage.DEAL.value:         "🤝 Shartnoma",
    PipelineStage.INSTALLATION.value: "🔧 O'rnatish",
    PipelineStage.COMPLETED.value:    "✅ Yakunlandi",
    PipelineStage.LOST.value:         "❌ Yo'qotildi",
}


def stage_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for value, label in _STAGE_LABELS.items():
        builder.row(InlineKeyboardButton(
            text=label,
            callback_data=f"bcast:stage:{value}",
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="bcast:back:seg"))
    return builder.as_markup()


# ── Payload type chooser ──────────────────────────────────────────────────────

def payload_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✍️ Matn", callback_data="bcast:pay:text"),
        InlineKeyboardButton(text="🖼 Rasm", callback_data="bcast:pay:photo"),
    )
    builder.row(
        InlineKeyboardButton(text="🎥 Video", callback_data="bcast:pay:video"),
        InlineKeyboardButton(text="📄 Hujjat", callback_data="bcast:pay:document"),
    )
    builder.row(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="bcast:cancel"))
    return builder.as_markup()


# ── Confirm / cancel ──────────────────────────────────────────────────────────

def confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Yuborish", callback_data="bcast:confirm"),
        InlineKeyboardButton(text="❌ Bekor", callback_data="bcast:cancel"),
    )
    return builder.as_markup()
