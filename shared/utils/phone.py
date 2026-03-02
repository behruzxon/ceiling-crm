"""Phone number utilities."""
from __future__ import annotations
import re

UZ_PHONE_REGEX = re.compile(r"^\+?998[0-9]{9}$")

# Matches: +998XXXXXXXXX, 998XXXXXXXXX, 9XXXXXXXX (9-digit local), with optional
# spaces/dashes between digit groups (e.g. "90 886 66 66", "90-886-66-66").
_PHONE_EXTRACT_RE = re.compile(
    r'\+?(?:998)?\s*\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
)


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


def extract_phone_from_text(text: str) -> str | None:
    """Find first valid UZ phone number in free text.

    Returns ``+998XXXXXXXXX`` or ``None`` if nothing valid is found.
    """
    for match in _PHONE_EXTRACT_RE.finditer(text):
        phone = normalize_phone(match.group(0))
        if phone and is_valid_uz_phone(phone):
            return phone
    return None
