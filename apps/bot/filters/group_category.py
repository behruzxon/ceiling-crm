"""
Group category filter.
Passes only for updates from groups with the specified category.
"""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject

from shared.constants.enums import CeilingCategory


class CategoryFilter(BaseFilter):
    """Passes if data["category"] matches one of the given categories."""

    def __init__(self, *categories: CeilingCategory) -> None:
        self.categories = frozenset(categories)

    async def __call__(self, event: TelegramObject, category: str | None = None, **data) -> bool:
        return category in self.categories
