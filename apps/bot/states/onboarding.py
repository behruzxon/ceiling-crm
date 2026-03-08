"""FSM states for the SaaS tenant onboarding wizard."""
from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    business_name = State()
    slug = State()
    business_type = State()
    bot_token = State()
    bot_username = State()
    admin_group_id = State()
    main_group_id = State()
    ai_prompt_choice = State()
    ai_prompt_custom = State()
    # Auto-generate prompt sub-flow
    ai_gen_description = State()
    ai_gen_audience = State()
    ai_gen_tone = State()
    ai_gen_preview = State()
    knowledge_base_choice = State()
    knowledge_base_custom = State()
    menu_config_choice = State()
    menu_config_custom = State()
    confirmation = State()
