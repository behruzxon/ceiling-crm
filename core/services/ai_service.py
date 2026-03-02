"""
AIService — guardrailed ceiling FAQ assistant.
Only answers questions about stretch ceilings. Never goes off-topic.
"""
from __future__ import annotations
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = """
Sen "VashPotolok" kompaniyasining natijnoy patalok bo'yicha sun'iy intellekt yordamchisisan.
Faqat natijnoy patalok haqida javob ber. Boshqa mavzular bo'yicha "Bu mavzu men uchun emas"
deb javob ber. Javoblar qisqa, ishonchli va sotuvga yo'naltirilgan bo'lsin.
"""


class AIService:
    """
    Wraps OpenAI GPT-4o with ceiling-domain guardrails.
    Max response: 512 tokens. Temperature: 0.3 (factual, not creative).
    All off-topic requests are deflected politely.
    """

    def __init__(self) -> None:
        self._settings = get_settings().openai

    async def answer_question(self, question: str, user_id: int) -> str:
        """
        Answer a ceiling-related question.
        Returns deflection message for off-topic questions.
        TODO: implement OpenAI call with token counting.
        """
        raise NotImplementedError

    def _is_on_topic(self, question: str) -> bool:
        """
        Quick keyword check before calling AI API.
        Saves tokens on obviously off-topic questions.
        TODO: implement keyword list.
        """
        raise NotImplementedError
