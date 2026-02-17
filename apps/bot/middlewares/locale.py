"""
Locale middleware.
Detects user language preference and injects translator function.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from shared.config import get_settings


# Lazy-loaded message dictionaries
_messages_cache: dict[str, dict[str, str]] = {}


def _load_messages(locale: str) -> dict[str, str]:
    """Load message dictionary for a locale."""
    if locale in _messages_cache:
        return _messages_cache[locale]

    try:
        if locale == "uz":
            from shared.i18n.locales.uz.messages import MESSAGES
        elif locale == "ru":
            try:
                from shared.i18n.locales.ru.messages import MESSAGES
            except ImportError:
                from shared.i18n.locales.uz.messages import MESSAGES
        elif locale == "en":
            try:
                from shared.i18n.locales.en.messages import MESSAGES
            except ImportError:
                from shared.i18n.locales.uz.messages import MESSAGES
        else:
            from shared.i18n.locales.uz.messages import MESSAGES

        _messages_cache[locale] = MESSAGES
        return MESSAGES
    except ImportError:
        return {}


def _make_translator(messages: dict[str, str]) -> Callable[..., str]:
    """Create a translator function that looks up keys in the messages dict."""
    def translate(key: str, **kwargs: object) -> str:
        template = messages.get(key, key)
        if kwargs:
            try:
                return template.format(**kwargs)
            except (KeyError, IndexError):
                return template
        return template
    return translate


class LocaleMiddleware(BaseMiddleware):
    """
    Injects data["_"] (translator function) and data["locale"]
    into every handler.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        db_user = data.get("db_user")

        # Priority: db_user preference > telegram language > default
        if db_user and hasattr(db_user, "language_code"):
            locale = db_user.language_code
        else:
            tg_user = data.get("event_from_user")
            locale = getattr(tg_user, "language_code", None) or settings.business.default_language

        # Ensure locale is supported
        if locale not in settings.business.supported_languages:
            locale = settings.business.default_language

        messages = _load_messages(locale)

        data["locale"] = locale
        data["_"] = _make_translator(messages)

        return await handler(event, data)
