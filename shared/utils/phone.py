"""Phone number utilities."""
from __future__ import annotations
import re

UZ_PHONE_REGEX = re.compile(r"^\+?998[0-9]{9}$")


def normalize_phone(raw: str) -> str | None:
    """
    Normalize Uzbek phone to +998XXXXXXXXX format.
    Returns None if the number is invalid.
    """
    digits = re.sub(r"[^\d]", "", raw)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    if len(digits) == 9:
        return f"+998{digits}"
    return None


def is_valid_uz_phone(phone: str) -> bool:
    return bool(UZ_PHONE_REGEX.match(phone))
