"""
shared.templates.followup_templates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Template-based follow-up messages for the user-facing re-engagement system.

3 stages x 5 business types.  Personalized with lead name when available.
"""
from __future__ import annotations


# ── Stage messages per business type ─────────────────────────────────────────
# Keys: business_type string (matches BusinessType enum values)
# Values: {stage_number: message_text}

_TEMPLATES: dict[str, dict[int, str]] = {
    "ceiling": {
        1: (
            "Natijnoy potolok bo'yicha savollaringiz bormi? "
            "Bepul maslahat beramiz \U0001f642"
        ),
        2: (
            "Xonangiz uchun bepul o'lchov xizmati mavjud! "
            "Usta kelib aniq narx aytadi. Qaysi tuman qulay?"
        ),
        3: (
            "Kerak bo'lganda yozing \u2014 har doim yordam berishga tayyormiz! \U0001f64f"
        ),
    },
    "restaurant": {
        1: "Buyurtma berishga yordam kerakmi? \U0001f642",
        2: (
            "Bugungi maxsus taklif bilan buyurtma bering! "
            "Yetkazib berish bepul \U0001f697"
        ),
        3: (
            "Istagan vaqt buyurtma berishingiz mumkin. "
            "Yoqimli ishtaha tilaymiz! \U0001f37d"
        ),
    },
    "auto_service": {
        1: "Avtomobilingiz uchun xizmat kerakmi? Yordam beramiz \U0001f642",
        2: (
            "Bepul diagnostika xizmati mavjud! "
            "Qachon kelishingiz qulay?"
        ),
        3: (
            "Kerak bo'lganda yozing \u2014 ustalarimiz har doim tayyor! \U0001f64f"
        ),
    },
    "clinic": {
        1: "Sog'liq bo'yicha savollaringiz bormi? Yordam beramiz \U0001f642",
        2: (
            "Mutaxassis bilan bepul maslahat olishingiz mumkin! "
            "Qachon qulay?"
        ),
        3: (
            "Kerak bo'lganda yozing \u2014 sog'ligingiz bizga muhim! \U0001f64f"
        ),
    },
    "other": {
        1: "Sizga yordam bera olamizmi? \U0001f642",
        2: (
            "Bizning maxsus takliflarimiz bilan tanishing! "
            "Savollaringiz bo'lsa yozing \U0001f4ac"
        ),
        3: (
            "Kerak bo'lganda qaytib yozing \u2014 doim shu yerdamiz! \U0001f64f"
        ),
    },
}

# Greeting prefix for all first messages
_GREETING = "Salom!"


def get_followup_message(
    stage: int,
    business_type: str,
    name: str | None = None,
) -> str:
    """Return the follow-up message for a given stage and business type.

    Personalizes with lead name when available.
    Falls back to 'other' type if business_type is not in templates.

    Args:
        stage: 1, 2, or 3
        business_type: e.g. "ceiling", "restaurant", "other"
        name: lead's name for personalization (optional)

    Returns:
        Ready-to-send message string.
    """
    templates = _TEMPLATES.get(business_type, _TEMPLATES["other"])
    text = templates.get(stage, templates.get(1, ""))

    if name:
        return f"{name}, {text[:1].lower()}{text[1:]}"

    if stage == 1:
        return f"{_GREETING} {text}"

    return text
