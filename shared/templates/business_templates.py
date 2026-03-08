"""Business templates for SaaS tenant onboarding.

Each template provides sensible defaults for ai_system_prompt,
knowledge_base, and menu_config so new tenants can start immediately
with minimal configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BusinessType(str, Enum):
    CEILING = "ceiling"
    RESTAURANT = "restaurant"
    AUTO_SERVICE = "auto_service"
    CLINIC = "clinic"
    OTHER = "other"


@dataclass(frozen=True)
class BusinessTemplate:
    """Immutable preset for a business vertical."""

    business_type: BusinessType
    label: str
    ai_system_prompt: str
    knowledge_base: str
    menu_config: dict = field(default_factory=dict)


# ── Menu presets ──────────────────────────────────────────────────────────────

_CEILING_MENU: dict = {
    "buttons": [
        ["\U0001f6d2 Zakaz berish", "\U0001f4b0 Narx kalkulyator"],
        ["\U0001f4c2 Katalog", "\U0001f381 Tayyor paketlar"],
        ["\U0001f4e6 Buyurtmalarim", "\u260e\ufe0f Operator"],
        ["\U0001f389 Chegirmalar", "\U0001f916 AI yordam"],
        ["\u2b50 Biz haqimizda"],
    ],
    "admin_buttons": [["\U0001f4e3 Rassilka"]],
}

_RESTAURANT_MENU: dict = {
    "buttons": [
        ["\U0001f4cb Menyu", "\U0001f6d2 Buyurtma berish"],
        ["\U0001f4cd Filiallar", "\u260e\ufe0f Operator"],
        ["\U0001f389 Aksiyalar", "\U0001f916 AI yordam"],
    ],
    "admin_buttons": [["\U0001f4e3 Rassilka"]],
}

_AUTO_SERVICE_MENU: dict = {
    "buttons": [
        ["\U0001f6e0\ufe0f Xizmatlar", "\U0001f4b0 Narxlar"],
        ["\U0001f4c5 Yozilish", "\u260e\ufe0f Operator"],
        ["\U0001f389 Aksiyalar", "\U0001f916 AI yordam"],
    ],
    "admin_buttons": [["\U0001f4e3 Rassilka"]],
}

_CLINIC_MENU: dict = {
    "buttons": [
        ["\U0001fa7a Xizmatlar", "\U0001f468\u200d\u2695\ufe0f Shifokorlar"],
        ["\U0001f4c5 Qabulga yozilish", "\u260e\ufe0f Operator"],
        ["\U0001f389 Aksiyalar", "\U0001f916 AI yordam"],
    ],
    "admin_buttons": [["\U0001f4e3 Rassilka"]],
}

_OTHER_MENU: dict = {
    "buttons": [
        ["\U0001f4cb Xizmatlar", "\U0001f4b0 Narxlar"],
        ["\U0001f6d2 Buyurtma", "\u260e\ufe0f Bog'lanish"],
        ["\U0001f916 AI yordam"],
    ],
    "admin_buttons": [["\U0001f4e3 Rassilka"]],
}


# ── Template definitions ──────────────────────────────────────────────────────

TEMPLATES: dict[BusinessType, BusinessTemplate] = {
    BusinessType.CEILING: BusinessTemplate(
        business_type=BusinessType.CEILING,
        label="Natyajnoy potolok",
        ai_system_prompt="",   # resolved lazily via get_ceiling_defaults()
        knowledge_base="",     # resolved lazily via get_ceiling_defaults()
        menu_config=_CEILING_MENU,
    ),
    BusinessType.RESTAURANT: BusinessTemplate(
        business_type=BusinessType.RESTAURANT,
        label="Restoran",
        ai_system_prompt=(
            "Sen {business_name} restoranining yordamchi botisan.\n"
            "Faqat o'zbek tilida javob ber. 3-5 jumla.\n"
            "Menyu, narxlar, buyurtma va filiallar haqida yordam ber.\n\n"
            "Javobni faqat JSON formatda ber:\n"
            '{{"intent":"greeting|menu|order|faq|other",'
            '"reply":"...","lead_temperature":"hot|warm|cold",'
            '"closing_confidence":0.0,'
            '"extracted":{{"interested_item":null,"location":null}}}}'
        ),
        knowledge_base="# {business_name} - Bilimlar bazasi\n\nMenyu va narxlar bu yerga qo'shiladi.",
        menu_config=_RESTAURANT_MENU,
    ),
    BusinessType.AUTO_SERVICE: BusinessTemplate(
        business_type=BusinessType.AUTO_SERVICE,
        label="Avtoservis",
        ai_system_prompt=(
            "Sen {business_name} avtoservisining yordamchi botisan.\n"
            "Faqat o'zbek tilida javob ber. 3-5 jumla.\n"
            "Xizmatlar, narxlar va yozilish haqida yordam ber.\n\n"
            "Javobni faqat JSON formatda ber:\n"
            '{{"intent":"greeting|service|booking|faq|other",'
            '"reply":"...","lead_temperature":"hot|warm|cold",'
            '"closing_confidence":0.0,'
            '"extracted":{{"interested_service":null,"car_model":null}}}}'
        ),
        knowledge_base="# {business_name} - Bilimlar bazasi\n\nXizmatlar va narxlar bu yerga qo'shiladi.",
        menu_config=_AUTO_SERVICE_MENU,
    ),
    BusinessType.CLINIC: BusinessTemplate(
        business_type=BusinessType.CLINIC,
        label="Klinika",
        ai_system_prompt=(
            "Sen {business_name} klinikasining yordamchi botisan.\n"
            "Faqat o'zbek tilida javob ber. 3-5 jumla.\n"
            "Xizmatlar, shifokorlar va qabulga yozilish haqida yordam ber.\n\n"
            "Javobni faqat JSON formatda ber:\n"
            '{{"intent":"greeting|service|appointment|faq|other",'
            '"reply":"...","lead_temperature":"hot|warm|cold",'
            '"closing_confidence":0.0,'
            '"extracted":{{"interested_service":null,"doctor":null}}}}'
        ),
        knowledge_base="# {business_name} - Bilimlar bazasi\n\nXizmatlar va shifokorlar ro'yxati bu yerga qo'shiladi.",
        menu_config=_CLINIC_MENU,
    ),
    BusinessType.OTHER: BusinessTemplate(
        business_type=BusinessType.OTHER,
        label="Boshqa",
        ai_system_prompt=(
            "Sen {business_name} biznesining yordamchi botisan.\n"
            "Faqat o'zbek tilida javob ber. 3-5 jumla.\n\n"
            "Javobni faqat JSON formatda ber:\n"
            '{{"intent":"greeting|info|order|faq|other",'
            '"reply":"...","lead_temperature":"hot|warm|cold",'
            '"closing_confidence":0.0,'
            '"extracted":{{}}}}'
        ),
        knowledge_base="# {business_name} - Bilimlar bazasi",
        menu_config=_OTHER_MENU,
    ),
}


def get_template(business_type: BusinessType) -> BusinessTemplate:
    """Return the template for a business type."""
    return TEMPLATES[business_type]


def resolve_template_text(text: str, business_name: str) -> str:
    """Replace {business_name} placeholder in template strings."""
    return text.replace("{business_name}", business_name)


# ── Welcome text templates (per business type) ──────────────────────────────

_WELCOME_TEMPLATES: dict[str, str] = {
    "ceiling": (
        "\U0001f916 {name} AI Bot\n\n"
        "Assalomu alaykum, {first_name}! \U0001f44b\n"
        "{name} kompaniyasining rasmiy AI yordamchisiga xush kelibsiz.\n\n"
        "Siz bu yerda:\n"
        "\U0001f4b0 Potolok narxini aniq hisoblay olasiz\n"
        "\U0001f3a8 Dizayn variantlarini ko\u02bbrishingiz mumkin\n"
        "\U0001f4c2 Real loyihalar katalogini ko\u02bbrasiz\n"
        "\U0001f9d1\u200d\U0001f527 Buyurtma qoldirib operator bilan bog\u02bblanasiz\n"
        "\U0001f916 AI yordamchi 24/7 savollaringizga javob beradi\n\n"
        "\U0001f447 Boshlash uchun kerakli bo\u02bblimni tanlang"
    ),
    "restaurant": (
        "\U0001f916 {name} Bot\n\n"
        "Assalomu alaykum, {first_name}! \U0001f44b\n"
        "{name} rasmiy botiga xush kelibsiz.\n\n"
        "Siz bu yerda:\n"
        "\U0001f4cb Menyuni ko\u02bbrishingiz mumkin\n"
        "\U0001f6d2 Buyurtma berishingiz mumkin\n"
        "\U0001f4cd Filiallarni topishingiz mumkin\n"
        "\U0001f916 AI yordamchi 24/7 savollaringizga javob beradi\n\n"
        "\U0001f447 Kerakli bo\u02bblimni tanlang"
    ),
    "auto_service": (
        "\U0001f916 {name} Bot\n\n"
        "Assalomu alaykum, {first_name}! \U0001f44b\n"
        "{name} rasmiy botiga xush kelibsiz.\n\n"
        "Siz bu yerda:\n"
        "\U0001f6e0\ufe0f Xizmatlar ro\u02bbyxatini ko\u02bbrasiz\n"
        "\U0001f4b0 Narxlar bilan tanishasiz\n"
        "\U0001f4c5 Xizmatga yozilasiz\n"
        "\U0001f916 AI yordamchi 24/7 savollaringizga javob beradi\n\n"
        "\U0001f447 Kerakli bo\u02bblimni tanlang"
    ),
    "clinic": (
        "\U0001f916 {name} Bot\n\n"
        "Assalomu alaykum, {first_name}! \U0001f44b\n"
        "{name} rasmiy botiga xush kelibsiz.\n\n"
        "Siz bu yerda:\n"
        "\U0001fa7a Xizmatlarni ko\u02bbrishingiz mumkin\n"
        "\U0001f468\u200d\u2695\ufe0f Shifokorlar haqida ma\u02bblumot olasiz\n"
        "\U0001f4c5 Qabulga yozilasiz\n"
        "\U0001f916 AI yordamchi 24/7 savollaringizga javob beradi\n\n"
        "\U0001f447 Kerakli bo\u02bblimni tanlang"
    ),
    "other": (
        "\U0001f916 {name} Bot\n\n"
        "Assalomu alaykum, {first_name}! \U0001f44b\n"
        "{name} rasmiy botiga xush kelibsiz.\n\n"
        "Siz bu yerda:\n"
        "\U0001f4cb Xizmatlar bilan tanishasiz\n"
        "\U0001f4b0 Narxlarni bilib olasiz\n"
        "\U0001f6d2 Buyurtma berasiz\n"
        "\U0001f916 AI yordamchi 24/7 savollaringizga javob beradi\n\n"
        "\U0001f447 Kerakli bo\u02bblimni tanlang"
    ),
}

OWNER_SECTION = (
    "\n\n\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
    "\U0001f454 Biznes boshqaruvi\n\n"
    "/my_business \u2014 Biznes sozlamalari\n"
    "/my_leads \u2014 CRM dashboard\n"
    "/edit_menu \u2014 Menyu tahrirlash"
)


def get_welcome_text(
    business_type: str,
    tenant_name: str,
    first_name: str,
    is_owner: bool = False,
) -> str:
    """Build tenant-aware welcome text from templates."""
    template = _WELCOME_TEMPLATES.get(business_type, _WELCOME_TEMPLATES["other"])
    text = template.format(name=tenant_name, first_name=first_name)
    if is_owner:
        text += OWNER_SECTION
    return text


def get_ceiling_defaults() -> tuple[str, str]:
    """Return (ai_system_prompt, knowledge_base) for the ceiling template.

    Lazily loaded to avoid circular imports at module level.
    """
    from apps.bot.ai.system_prompt import (
        get_default_knowledge_base,
        get_default_system_prompt,
    )

    return get_default_system_prompt(), get_default_knowledge_base()
