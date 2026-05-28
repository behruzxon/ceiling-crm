"""Phone number utilities."""

from __future__ import annotations

import re

UZ_PHONE_REGEX = re.compile(r"^\+?998[0-9]{9}$")

# Matches: +998XXXXXXXXX, 998XXXXXXXXX, 9XXXXXXXX (9-digit local), with optional
# spaces/dashes between digit groups (e.g. "90 886 66 66", "90-886-66-66").
_PHONE_EXTRACT_RE = re.compile(r"\+?(?:998)?\s*\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")

# Looser pattern for mask_phone_in_text — catches raw phones inside free text
# even when not in canonical form, so we never let one slip into logs.
_PHONE_MASK_RE = re.compile(
    r"\+?998[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
    r"|\b\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b"
)

# Mask format constants — kept as module-level so call sites and tests agree.
MASK_PREFIX_DIGITS = 4
MASK_SUFFIX_DIGITS = 2
MASK_FILL = "****"


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


def mask_phone(phone: str | None) -> str:
    """Return a privacy-preserving mask of *phone* for logs/admin previews.

    Preserves the leading ``+998`` (or first four characters) and the last two
    digits — enough for an operator to recognise the number when matched
    against CRM records, but not enough to dial. Short or empty inputs are
    returned unchanged or as an empty string.

    Examples
    --------
    >>> mask_phone("+998901234567")
    '+998****67'
    >>> mask_phone("901234567")
    '9012****67'
    >>> mask_phone(None)
    ''
    """
    if phone is None:
        return ""
    s = str(phone).strip()
    if not s:
        return ""
    if len(s) < MASK_PREFIX_DIGITS + MASK_SUFFIX_DIGITS:
        return s
    return f"{s[:MASK_PREFIX_DIGITS]}{MASK_FILL}{s[-MASK_SUFFIX_DIGITS:]}"


def mask_phone_in_text(text: str) -> str:
    """Replace any phone numbers inside free-form *text* with the masked form.

    Use at log/notification boundaries when the message contains user text
    that might quote a phone number. Safe to call with ``None`` / empty input.
    """
    if not text:
        return text or ""
    return _PHONE_MASK_RE.sub(lambda m: mask_phone(m.group(0)), text)
