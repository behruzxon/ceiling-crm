"""FSM states for the admin broadcast composer (private chat only)."""
from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    choosing_segment   = State()  # ALL / BY_STAGE / ADMIN_GROUPS
    choosing_stage     = State()  # pipeline stage picker (only for BY_STAGE)
    choosing_payload   = State()  # TEXT / PHOTO / VIDEO / DOCUMENT
    waiting_for_text   = State()  # collect text message
    waiting_for_media  = State()  # collect photo / video / document + optional caption
    confirming         = State()  # preview summary → confirm or cancel
