"""Encrypt existing plaintext bot tokens.

Reads all tenant rows with non-null bot_token, checks if each is
still plaintext (matches Telegram token format), encrypts it, and
writes the ciphertext back. Already-encrypted values are skipped.

Requires BOT_TOKEN_ENCRYPTION_KEY to be set in the environment.

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-03-09 19:00:00.000000+00:00
"""
from __future__ import annotations

import os
import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "z2a3b4c5d6e7"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None

_RAW_TOKEN_RE = re.compile(r"^\d{6,10}:[A-Za-z0-9_-]{30,50}$")
_FERNET_PREFIX = "gAAAAA"


def _is_plaintext(value: str) -> bool:
    """Check if a value looks like a raw Telegram bot token."""
    return bool(_RAW_TOKEN_RE.match(value.strip()))


def _is_encrypted(value: str) -> bool:
    """Check if a value looks like Fernet ciphertext."""
    return len(value) > 50 and value.startswith(_FERNET_PREFIX)


def upgrade() -> None:
    # Inline encryption to avoid importing app-level modules during migration
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    raw_key = os.environ.get("BOT_TOKEN_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        # Allow migration to pass in development without key
        # (no tokens to encrypt in a fresh DB)
        print(
            "WARNING: BOT_TOKEN_ENCRYPTION_KEY not set. "
            "Skipping token encryption. Set the key and re-run if "
            "you have existing plaintext tokens."
        )
        return

    # Build Fernet cipher (same logic as token_encryption.py)
    if len(raw_key) == 44 and raw_key.endswith("="):
        try:
            f = Fernet(raw_key.encode())
        except Exception:
            derived = hashlib.sha256(raw_key.encode()).digest()
            f = Fernet(base64.urlsafe_b64encode(derived))
    else:
        derived = hashlib.sha256(raw_key.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(derived))

    conn = op.get_bind()
    tenants = sa.table(
        "tenants",
        sa.column("id", sa.BigInteger),
        sa.column("bot_token", sa.String),
    )

    rows = conn.execute(
        sa.select(tenants.c.id, tenants.c.bot_token).where(
            tenants.c.bot_token.isnot(None),
        )
    ).fetchall()

    encrypted_count = 0
    skipped_count = 0

    for row in rows:
        tid, token = row.id, row.bot_token

        if not token or not token.strip():
            continue

        if _is_encrypted(token):
            skipped_count += 1
            continue

        if not _is_plaintext(token):
            print(f"  WARNING: tenant {tid} has unrecognized token format, skipping")
            skipped_count += 1
            continue

        ciphertext = f.encrypt(token.encode("utf-8")).decode("ascii")
        conn.execute(
            tenants.update()
            .where(tenants.c.id == tid)
            .values(bot_token=ciphertext)
        )
        encrypted_count += 1

    print(
        f"  Token encryption: {encrypted_count} encrypted, "
        f"{skipped_count} skipped (already encrypted or empty)"
    )


def downgrade() -> None:
    # Decryption on downgrade
    import base64
    import hashlib

    from cryptography.fernet import Fernet

    raw_key = os.environ.get("BOT_TOKEN_ENCRYPTION_KEY", "").strip()
    if not raw_key:
        print(
            "WARNING: BOT_TOKEN_ENCRYPTION_KEY not set. "
            "Cannot decrypt tokens during downgrade."
        )
        return

    if len(raw_key) == 44 and raw_key.endswith("="):
        try:
            f = Fernet(raw_key.encode())
        except Exception:
            derived = hashlib.sha256(raw_key.encode()).digest()
            f = Fernet(base64.urlsafe_b64encode(derived))
    else:
        derived = hashlib.sha256(raw_key.encode()).digest()
        f = Fernet(base64.urlsafe_b64encode(derived))

    conn = op.get_bind()
    tenants = sa.table(
        "tenants",
        sa.column("id", sa.BigInteger),
        sa.column("bot_token", sa.String),
    )

    rows = conn.execute(
        sa.select(tenants.c.id, tenants.c.bot_token).where(
            tenants.c.bot_token.isnot(None),
        )
    ).fetchall()

    decrypted_count = 0

    for row in rows:
        tid, token = row.id, row.bot_token

        if not token or not _is_encrypted(token):
            continue

        try:
            plaintext = f.decrypt(token.encode("ascii")).decode("utf-8")
            conn.execute(
                tenants.update()
                .where(tenants.c.id == tid)
                .values(bot_token=plaintext)
            )
            decrypted_count += 1
        except Exception:
            print(f"  WARNING: Failed to decrypt token for tenant {tid}")

    print(f"  Token decryption: {decrypted_count} decrypted")
