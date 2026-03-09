"""
core.security.token_encryption
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Fernet symmetric encryption for tenant bot tokens at rest.

The encryption key is derived from the ``BOT_TOKEN_ENCRYPTION_KEY`` env var.
If the key is missing or empty, a ``RuntimeError`` is raised on first use
to ensure tokens are never stored in plaintext unintentionally.

Usage::

    from core.security.token_encryption import encrypt_token, decrypt_token

    ciphertext = encrypt_token("123456:ABC-DEF...")
    plaintext  = decrypt_token(ciphertext)
    assert plaintext == "123456:ABC-DEF..."
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from shared.logging import get_logger

log = get_logger(__name__)

# Telegram bot token format: {bot_id}:{secret}
_RAW_TOKEN_RE = re.compile(r"^\d{6,10}:[A-Za-z0-9_-]{30,50}$")

# Fernet ciphertext always starts with "gAAAAA" (base64-encoded version byte)
_FERNET_PREFIX = "gAAAAA"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build and cache the Fernet cipher from the env-var key.

    Reads BOT_TOKEN_ENCRYPTION_KEY from the environment (directly or via
    Settings). The raw key is hashed with SHA-256 to produce exactly 32 bytes,
    then base64-encoded to satisfy Fernet's 32-byte url-safe-b64 requirement.
    This allows any passphrase length as input.
    """
    # Try Settings first, fall back to raw env var
    raw_key = ""
    try:
        from shared.config import get_settings
        settings = get_settings()
        raw_key = settings.bot_token_encryption_key.get_secret_value().strip()
    except Exception:
        pass

    # Fall back to env var if settings didn't provide a key
    # (e.g. settings lru_cache was populated before env var was set)
    if not raw_key:
        raw_key = os.environ.get("BOT_TOKEN_ENCRYPTION_KEY", "").strip()

    if not raw_key:
        raise RuntimeError(
            "BOT_TOKEN_ENCRYPTION_KEY environment variable is required "
            "for bot token encryption. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    # If the key is already a valid Fernet key (44 chars, base64), use it directly
    if len(raw_key) == 44 and raw_key.endswith("="):
        try:
            return Fernet(raw_key.encode())
        except Exception:
            pass

    # Otherwise derive a 32-byte key from the passphrase via SHA-256
    derived = hashlib.sha256(raw_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def encrypt_token(token: str) -> str:
    """Encrypt a plaintext bot token and return the ciphertext as a string.

    Raises ``RuntimeError`` if the encryption key is not configured.
    """
    if not token or not token.strip():
        raise ValueError("Cannot encrypt empty token")

    f = _get_fernet()
    ciphertext = f.encrypt(token.encode("utf-8"))
    return ciphertext.decode("ascii")


def decrypt_token(encrypted: str) -> str:
    """Decrypt a Fernet-encrypted bot token back to plaintext.

    Raises ``cryptography.fernet.InvalidToken`` if the ciphertext is
    corrupted or was encrypted with a different key.
    Raises ``RuntimeError`` if the encryption key is not configured.
    """
    if not encrypted or not encrypted.strip():
        raise ValueError("Cannot decrypt empty value")

    f = _get_fernet()
    plaintext = f.decrypt(encrypted.encode("ascii"))
    return plaintext.decode("utf-8")


def is_encrypted(value: str) -> bool:
    """Check whether a stored value looks like Fernet ciphertext.

    Useful during migration to distinguish plaintext tokens from
    already-encrypted ones.
    """
    if not value or len(value) < 50:
        return False
    # Fernet ciphertext is base64 and always starts with "gAAAAA"
    return value.startswith(_FERNET_PREFIX)


def is_raw_bot_token(value: str) -> bool:
    """Check whether a value matches the Telegram bot token format."""
    return bool(_RAW_TOKEN_RE.match(value.strip()))


def mask_token(token: str) -> str:
    """Mask a token for safe display: show first 4 and last 4 chars only."""
    if len(token) <= 10:
        return "****"
    return f"{token[:4]}...{token[-4:]}"
