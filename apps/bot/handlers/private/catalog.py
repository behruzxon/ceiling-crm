"""
Catalog browsing handler.
Shows category-specific ceiling catalog with images and pricing.
"""
from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name="private:catalog")


@router.message(Command("catalog"))
async def cmd_catalog(message: Message, **data) -> None:
    """Entry point for catalog flow. TODO: show category selection."""
    raise NotImplementedError


@router.message(F.text == "📸 Katalog")
async def btn_catalog(message: Message, **data) -> None:
    """Keyboard button handler for catalog. TODO: same as cmd_catalog."""
    raise NotImplementedError
