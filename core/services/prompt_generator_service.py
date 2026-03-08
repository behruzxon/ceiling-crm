"""
core.services.prompt_generator_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic template-based AI system prompt generator.

Builds a structured prompt from business inputs without calling OpenAI.
Compatible with the existing JSON response format expected by _call_ai().
"""
from __future__ import annotations

from dataclasses import dataclass

from shared.templates.business_templates import BusinessType


@dataclass(frozen=True)
class PromptInputs:
    """Structured inputs for prompt generation."""

    business_name: str
    business_type: BusinessType
    description: str
    target_audience: str
    region: str = "O'zbekiston"
    language: str = "uz"
    tone: str = "professional"


# Intent options per business type
_INTENTS: dict[BusinessType, str] = {
    BusinessType.CEILING: "greeting|price|catalog|operator|measurement|faq|objection|other",
    BusinessType.RESTAURANT: "greeting|menu|order|faq|other",
    BusinessType.AUTO_SERVICE: "greeting|service|booking|faq|other",
    BusinessType.CLINIC: "greeting|service|appointment|faq|other",
    BusinessType.OTHER: "greeting|info|order|faq|other",
}

# Extracted fields per business type
_EXTRACTED_FIELDS: dict[BusinessType, dict[str, None]] = {
    BusinessType.CEILING: {
        "interested_design": None,
        "last_dimensions": None,
        "location": None,
    },
    BusinessType.RESTAURANT: {"interested_item": None, "location": None},
    BusinessType.AUTO_SERVICE: {"interested_service": None, "car_model": None},
    BusinessType.CLINIC: {"interested_service": None, "doctor": None},
    BusinessType.OTHER: {},
}

_TONE_INSTRUCTIONS: dict[str, str] = {
    "professional": "Professional va ishonchli ohangda gapir.",
    "friendly": "Do'stona va samimiy ohangda gapir.",
    "formal": "Rasmiy va hurmatli ohangda gapir.",
}

_LANG_NAMES: dict[str, str] = {
    "uz": "o'zbek",
    "ru": "rus",
    "en": "ingliz",
}


def generate_prompt(inputs: PromptInputs) -> str:
    """Generate a complete AI system prompt from structured inputs.

    Returns a prompt string compatible with the existing AI stack
    (JSON response format with intent/reply/lead_temperature/closing_confidence/extracted).
    """
    intents = _INTENTS.get(inputs.business_type, _INTENTS[BusinessType.OTHER])
    extracted = _EXTRACTED_FIELDS.get(inputs.business_type, {})
    tone_instruction = _TONE_INSTRUCTIONS.get(inputs.tone, _TONE_INSTRUCTIONS["professional"])

    extracted_json = ", ".join(f'"{k}": null' for k in extracted) if extracted else ""

    sections = [
        _build_role_section(inputs),
        _build_rules_section(inputs, tone_instruction),
        _build_greeting_section(inputs),
        _build_sales_section(),
        _build_lead_scoring_section(),
        _build_closing_confidence_section(),
        _build_response_format_section(intents, extracted_json),
    ]

    return "\n\n".join(sections).strip()


def _build_role_section(inputs: PromptInputs) -> str:
    return (
        f'Sen "{inputs.business_name}" biznesining tajribali savdo menejeri '
        f"va botdagi yordamchisisan.\n"
        f"Biznes haqida: {inputs.description}\n"
        f"Maqsadli auditoriya: {inputs.target_audience}\n"
        f"Xizmat hududi: {inputs.region}"
    )


def _build_rules_section(inputs: PromptInputs, tone: str) -> str:
    lang_name = _LANG_NAMES.get(inputs.language, "o'zbek")
    return (
        "========================\n"
        "ASOSIY QOIDALAR\n"
        "========================\n"
        f"- Faqat {lang_name} tilida javob ber.\n"
        "- 3-5 jumladan oshirma.\n"
        "- 1-2 ta mos emoji ishlat (haddan oshma).\n"
        "- Keraksiz uzun matn yozma.\n"
        f"- {tone}\n"
        f"- Faqat {inputs.business_name} bilan bog'liq mavzularda gapir.\n"
        "- Boshqa mavzuda so'ralsa, foydalanuvchini asosiy "
        "xizmatlar haqida so'rashga yo'naltir.\n\n"
        "TAQIQLANGAN:\n"
        '- Hech qachon "yozib qo\'ydim", "operator bog\'lanadi" dema '
        "— bu faqat real FSM orqali bo'ladi.\n"
        '- "Zo\'r", "Ok", "Ha" kabi qisqa javoblardan xulosa chiqarma.'
    )


def _build_greeting_section(inputs: PromptInputs) -> str:
    return (
        "========================\n"
        "SALOMLASHISH\n"
        "========================\n"
        "Agar foydalanuvchi faqat salomlashsa:\n"
        "- Qisqa, iliq javob ber (1-2 jumla).\n"
        f"- {inputs.business_name} xizmatlari haqida bitta neytral savol ber.\n"
        '- intent = "greeting"'
    )


def _build_sales_section() -> str:
    return (
        "========================\n"
        "SAVDO STRATEGIYASI\n"
        "========================\n"
        "1) Ma'lumot so'rasa: aniq va qisqa javob ber.\n"
        "2) Ikkilanayotgan bo'lsa: bepul maslahat yoki chegirmani taklif qil.\n"
        '3) "Qimmat" desa: arzon variantlarni taqdim et va sifat kafolatini eslat.\n'
        '4) "Keyinroq" desa: majburiyatsiz bepul konsultatsiyani taklif qil.'
    )


def _build_lead_scoring_section() -> str:
    return (
        "========================\n"
        "LEAD SCORING\n"
        "========================\n"
        "Hot:\n"
        "- Aniq xizmat yoki mahsulot so'radi\n"
        "- Manzil yoki vaqt berdi\n"
        "- Buyurtma qilishga tayyor\n\n"
        "Warm:\n"
        "- Narx so'radi\n"
        "- Xizmatlar qiziqdi\n\n"
        "Cold:\n"
        "- Faqat umumiy savol\n\n"
        "Har javobda ichki bahola:\n"
        "lead_temperature = hot | warm | cold"
    )


def _build_closing_confidence_section() -> str:
    return (
        "========================\n"
        "CLOSING CONFIDENCE\n"
        "========================\n"
        "Foydalanuvchi tayyorlik darajasi:\n"
        "0.0 - 1.0 oralig'ida bahola.\n\n"
        "0.8+ -> yopishga harakat qil\n"
        "0.5-0.8 -> yumshoq CTA\n"
        "0-0.5 -> faqat ma'lumot ber"
    )


def _build_response_format_section(intents: str, extracted_json: str) -> str:
    extracted_block = f"{{{extracted_json}}}" if extracted_json else "{}"
    return (
        "========================\n"
        "JAVOB FORMATI\n"
        "========================\n"
        "Faqat to'g'ri JSON. Hech qanday qo'shimcha matn yo'q.\n\n"
        "{{\n"
        f'  "intent": "{intents}",\n'
        '  "reply": "...",\n'
        '  "lead_temperature": "hot|warm|cold",\n'
        '  "closing_confidence": 0.0,\n'
        f'  "extracted": {extracted_block}\n'
        "}}"
    )
