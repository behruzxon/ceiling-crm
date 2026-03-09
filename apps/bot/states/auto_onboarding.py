"""FSM states for the simplified automatic SaaS onboarding wizard."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AutoOnboardingStates(StatesGroup):
    """Streamlined 4-step onboarding: name → type → token → confirm."""

    company_name = State()
    industry_type = State()
    bot_token = State()
    confirmation = State()
