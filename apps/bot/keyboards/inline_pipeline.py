"""Inline keyboard builder for pipeline stage transitions."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.constants.enums import PipelineStage


def pipeline_actions_keyboard(lead_id: int, current_stage: PipelineStage) -> InlineKeyboardMarkup:
    """Build context-sensitive pipeline action keyboard. TODO: show only valid next stages."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏭ Keyingi bosqich", callback_data=f"pipeline:advance:{lead_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📅 Uchrashuv", callback_data=f"pipeline:schedule:{lead_id}"
                )
            ],
            [InlineKeyboardButton(text="❌ Yo'qotildi", callback_data=f"pipeline:lost:{lead_id}")],
        ]
    )
