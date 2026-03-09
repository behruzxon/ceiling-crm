"""FSM states for tenant bot connection management."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class TenantBotConnectStates(StatesGroup):
    """Connect a new bot: token -> confirm."""

    waiting_for_token = State()
    confirm_connect = State()


class TenantBotDisconnectStates(StatesGroup):
    """Disconnect: confirm."""

    confirm_disconnect = State()


class TenantBotReconnectStates(StatesGroup):
    """Reconnect with new token: new token -> confirm."""

    waiting_for_new_token = State()
    confirm_reconnect = State()
