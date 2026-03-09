"""Unit tests for bot token encryption.

Covers:
  1. encrypt_token / decrypt_token roundtrip
  2. Encrypted output does NOT match raw token format
  3. is_encrypted / is_raw_bot_token detection
  4. mask_token display safety
  5. Error cases: empty input, wrong key, missing key
  6. Migration compatibility: plaintext detection
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest


# ── Fixture: set a test encryption key ─────────────────────────────────────

@pytest.fixture(autouse=True)
def _set_encryption_key(monkeypatch):
    """Set a deterministic encryption key for all tests."""
    monkeypatch.setenv("BOT_TOKEN_ENCRYPTION_KEY", "test-key-for-unit-tests-only-not-production")
    # Clear the lru_cache so each test gets a fresh Fernet instance
    from core.security.token_encryption import _get_fernet
    _get_fernet.cache_clear()
    yield
    _get_fernet.cache_clear()


# ── Roundtrip tests ────────────────────────────────────────────────────────


class TestEncryptDecryptRoundtrip:
    """encrypt(token) -> decrypt -> original token."""

    def test_roundtrip_basic(self) -> None:
        from core.security.token_encryption import decrypt_token, encrypt_token

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == token

    def test_roundtrip_various_tokens(self) -> None:
        from core.security.token_encryption import decrypt_token, encrypt_token

        tokens = [
            "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "9876543210:abcdefghijklmnopqrstuvwxyz1234567890ABCD",
            "1111111:A_B-C_D-E_F-G_H-I_J-K_L-M_N-O_P-Q",
        ]
        for token in tokens:
            encrypted = encrypt_token(token)
            assert decrypt_token(encrypted) == token

    def test_encrypted_output_differs_from_input(self) -> None:
        from core.security.token_encryption import encrypt_token

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)

        assert encrypted != token
        assert len(encrypted) > len(token)

    def test_same_token_encrypts_differently_each_time(self) -> None:
        """Fernet includes a timestamp nonce, so each encryption is unique."""
        from core.security.token_encryption import encrypt_token

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        e1 = encrypt_token(token)
        e2 = encrypt_token(token)

        assert e1 != e2  # Different ciphertexts due to timestamp


# ── Format detection tests ─────────────────────────────────────────────────


class TestFormatDetection:
    """is_encrypted and is_raw_bot_token correctly classify values."""

    def test_encrypted_detected(self) -> None:
        from core.security.token_encryption import encrypt_token, is_encrypted

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)

        assert is_encrypted(encrypted) is True

    def test_plaintext_not_detected_as_encrypted(self) -> None:
        from core.security.token_encryption import is_encrypted

        assert is_encrypted("1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx") is False
        assert is_encrypted("short") is False
        assert is_encrypted("") is False

    def test_raw_token_detected(self) -> None:
        from core.security.token_encryption import is_raw_bot_token

        assert is_raw_bot_token("1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx") is True
        assert is_raw_bot_token("123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA") is True

    def test_encrypted_not_raw_token(self) -> None:
        from core.security.token_encryption import (
            encrypt_token,
            is_raw_bot_token,
        )

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)

        assert is_raw_bot_token(encrypted) is False

    def test_garbage_not_raw_token(self) -> None:
        from core.security.token_encryption import is_raw_bot_token

        assert is_raw_bot_token("hello world") is False
        assert is_raw_bot_token("") is False
        assert is_raw_bot_token("12345:short") is False


# ── Mask token tests ───────────────────────────────────────────────────────


class TestMaskToken:
    """mask_token hides the middle of a token."""

    def test_mask_normal_token(self) -> None:
        from core.security.token_encryption import mask_token

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        masked = mask_token(token)

        assert masked.startswith("1234")
        assert masked.endswith("xxxx")
        assert "..." in masked
        # Must not contain the full token
        assert token not in masked

    def test_mask_short_value(self) -> None:
        from core.security.token_encryption import mask_token

        assert mask_token("short") == "****"
        assert mask_token("") == "****"


# ── Error cases ────────────────────────────────────────────────────────────


class TestErrorCases:
    """Edge cases and error handling."""

    def test_encrypt_empty_raises(self) -> None:
        from core.security.token_encryption import encrypt_token

        with pytest.raises(ValueError, match="empty"):
            encrypt_token("")

    def test_decrypt_empty_raises(self) -> None:
        from core.security.token_encryption import decrypt_token

        with pytest.raises(ValueError, match="empty"):
            decrypt_token("")

    def test_decrypt_garbage_raises(self) -> None:
        from core.security.token_encryption import decrypt_token

        with pytest.raises(Exception):  # InvalidToken or similar
            decrypt_token("not-a-valid-fernet-ciphertext-at-all")

    def test_decrypt_wrong_key_raises(self) -> None:
        from core.security.token_encryption import _get_fernet, encrypt_token

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)

        # Build a Fernet with a completely different key
        import base64
        import hashlib

        from cryptography.fernet import Fernet, InvalidToken

        wrong_derived = hashlib.sha256(b"wrong-key-entirely").digest()
        wrong_f = Fernet(base64.urlsafe_b64encode(wrong_derived))

        with pytest.raises(InvalidToken):
            wrong_f.decrypt(encrypted.encode("ascii"))

    def test_missing_key_raises(self) -> None:
        from core.security.token_encryption import _get_fernet, encrypt_token

        _get_fernet.cache_clear()
        os.environ.pop("BOT_TOKEN_ENCRYPTION_KEY", None)

        # Patch get_settings to return empty key
        from unittest.mock import MagicMock
        mock_settings = MagicMock()
        mock_settings.bot_token_encryption_key.get_secret_value.return_value = ""

        with patch("shared.config.get_settings", return_value=mock_settings):
            with pytest.raises(RuntimeError, match="BOT_TOKEN_ENCRYPTION_KEY"):
                encrypt_token("1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx")


# ── Fernet key derivation tests ────────────────────────────────────────────


class TestKeyDerivation:
    """Test that various key formats work."""

    def test_passphrase_key(self) -> None:
        """Any passphrase works via SHA-256 derivation."""
        from core.security.token_encryption import decrypt_token, encrypt_token

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)

        assert decrypt_token(encrypted) == token

    def test_fernet_key_format(self) -> None:
        """A proper Fernet key (44 chars, base64, =) works directly."""
        from cryptography.fernet import Fernet

        from core.security.token_encryption import (
            _get_fernet,
            decrypt_token,
            encrypt_token,
        )

        # Generate a proper Fernet key
        proper_key = Fernet.generate_key().decode()
        assert len(proper_key) == 44
        assert proper_key.endswith("=")

        _get_fernet.cache_clear()
        os.environ["BOT_TOKEN_ENCRYPTION_KEY"] = proper_key

        token = "1234567890:AABBCCDDEEFFaabbccddeeff-xxxxxxxx"
        encrypted = encrypt_token(token)

        assert decrypt_token(encrypted) == token
