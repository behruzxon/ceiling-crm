"""
Group onboarding handler — superseded by welcome.py (C3-2).

The chat_member welcome logic has been moved to welcome.py.
This module is kept as a no-op stub so existing imports do not break
while the router is being phased out.
"""
from __future__ import annotations

from aiogram import Router

router = Router(name="group:onboarding")
