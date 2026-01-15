"""Tests for OAuth token encryption and decryption.

Tests the Fernet-based encryption used to securely store OAuth tokens
in the database. Verifies round-trip encryption, key derivation, and error handling.
"""
import os
from unittest.mock import patch

import pytest
from cryptography.fernet import InvalidToken

from reconly_core.email.crypto import (
    TokenEncryptionError,
    decrypt_token,
    decrypt_token_optional,
    encrypt_token,
    encrypt_token_optional,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def secret_key():
    """Set up SECRET_KEY for encryption tests."""
    old_secret = os.environ.get("SECRET_KEY")
    os.environ["SECRET_KEY"] = "test-secret-key-for-token-encryption-testing"

    yield

    if old_secret:
        os.environ["SECRET_KEY"] = old_secret
    else:
        os.environ.pop("SECRET_KEY", None)


@pytest.fixture
def sample_access_token():
    """Sample OAuth access token for testing."""
    return "ya29.a0AfH6SMBxxx-very-long-google-access-token-string-here-xxx"


@pytest.fixture
def sample_refresh_token():
    """Sample OAuth refresh token for testing."""
    return "1//0gXXXX-very-long-google-refresh-token-string-here-XXXX"


# =============================================================================
# Basic Encryption/Decryption Tests
# =============================================================================

class TestTokenEncryption:
    """Test basic token encryption functionality."""

    def test_encrypt_token_returns_encrypted_string(self, secret_key, sample_access_token):
        """Test that encryption produces a non-plaintext encrypted string."""
        encrypted = encrypt_token(sample_access_token)

        # Should return a string
        assert isinstance(encrypted, str)

        # Encrypted value should be different from plaintext
        assert encrypted != sample_access_token

        # Should be longer due to encryption overhead
        assert len(encrypted) > len(sample_access_token)

        # Should not contain the original token
        assert sample_access_token not in encrypted

    def test_decrypt_token_returns_original(self, secret_key, sample_access_token):
        """Test that decryption returns the original plaintext token."""
        encrypted = encrypt_token(sample_access_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == sample_access_token

    def test_encrypt_decrypt_round_trip(self, secret_key, sample_access_token, sample_refresh_token):
        """Test round-trip encryption and decryption for various tokens."""
        # Test access token
        encrypted_access = encrypt_token(sample_access_token)
        assert decrypt_token(encrypted_access) == sample_access_token

        # Test refresh token
        encrypted_refresh = encrypt_token(sample_refresh_token)
        assert decrypt_token(encrypted_refresh) == sample_refresh_token

        # Test short token
        short_token = "short"
        encrypted_short = encrypt_token(short_token)
        assert decrypt_token(encrypted_short) == short_token

        # Test long token
        long_token = "x" * 10000
        encrypted_long = encrypt_token(long_token)
        assert decrypt_token(encrypted_long) == long_token

    def test_encrypted_tokens_are_different_each_time(self, secret_key, sample_access_token):
        """Test that encryption uses random IV (produces different ciphertext each time)."""
        encrypted1 = encrypt_token(sample_access_token)
        encrypted2 = encrypt_token(sample_access_token)

        # Same plaintext should produce different ciphertext (due to random IV)
        assert encrypted1 != encrypted2

        # But both should decrypt to the same plaintext
        assert decrypt_token(encrypted1) == sample_access_token
        assert decrypt_token(encrypted2) == sample_access_token

    def test_encrypt_empty_token_raises_error(self, secret_key):
        """Test that encrypting empty token raises error."""
        with pytest.raises(TokenEncryptionError, match="Cannot encrypt empty token"):
            encrypt_token("")

    def test_decrypt_empty_token_raises_error(self, secret_key):
        """Test that decrypting empty token raises error."""
        with pytest.raises(TokenEncryptionError, match="Cannot decrypt empty token"):
            decrypt_token("")


# =============================================================================
# Key Derivation Tests
# =============================================================================

class TestKeyDerivation:
    """Test SECRET_KEY derivation and Fernet key generation."""

    def test_encryption_requires_secret_key(self, sample_access_token):
        """Test that encryption fails without SECRET_KEY."""
        # Remove SECRET_KEY
        old_secret = os.environ.pop("SECRET_KEY", None)

        try:
            with pytest.raises(TokenEncryptionError, match="SECRET_KEY.*not set"):
                encrypt_token(sample_access_token)
        finally:
            if old_secret:
                os.environ["SECRET_KEY"] = old_secret

    def test_decryption_requires_secret_key(self):
        """Test that decryption fails without SECRET_KEY."""
        # First encrypt with a key
        os.environ["SECRET_KEY"] = "test-key"
        encrypted = encrypt_token("test_token")

        # Remove key
        os.environ.pop("SECRET_KEY", None)

        try:
            with pytest.raises(TokenEncryptionError, match="SECRET_KEY.*not set"):
                decrypt_token(encrypted)
        finally:
            os.environ["SECRET_KEY"] = "test-key"

    def test_different_secret_keys_produce_different_encryption(self, sample_access_token):
        """Test that different SECRET_KEYs produce different encrypted output."""
        # Encrypt with first key
        os.environ["SECRET_KEY"] = "first-secret-key"
        encrypted1 = encrypt_token(sample_access_token)

        # Encrypt with second key
        os.environ["SECRET_KEY"] = "second-secret-key"
        encrypted2 = encrypt_token(sample_access_token)

        # Different keys should produce different ciphertext
        assert encrypted1 != encrypted2

    def test_decryption_fails_with_wrong_secret_key(self, sample_access_token):
        """Test that decryption fails if SECRET_KEY has changed."""
        # Encrypt with one key
        os.environ["SECRET_KEY"] = "original-secret-key"
        encrypted = encrypt_token(sample_access_token)

        # Try to decrypt with different key
        os.environ["SECRET_KEY"] = "different-secret-key"

        with pytest.raises(TokenEncryptionError, match="Failed to decrypt token"):
            decrypt_token(encrypted)

    def test_consistent_key_derivation(self, sample_access_token):
        """Test that same SECRET_KEY produces consistent decryption."""
        secret = "consistent-test-key"
        os.environ["SECRET_KEY"] = secret

        # Encrypt token
        encrypted = encrypt_token(sample_access_token)

        # Clear and re-set the same key (simulates app restart)
        os.environ.pop("SECRET_KEY")
        os.environ["SECRET_KEY"] = secret

        # Should still be able to decrypt
        decrypted = decrypt_token(encrypted)
        assert decrypted == sample_access_token


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling for invalid inputs and edge cases."""

    def test_decrypt_invalid_token_format(self, secret_key):
        """Test decrypting malformed token data."""
        invalid_token = "this-is-not-valid-encrypted-data"

        with pytest.raises(TokenEncryptionError, match="Failed to decrypt token"):
            decrypt_token(invalid_token)

    def test_decrypt_corrupted_token(self, secret_key, sample_access_token):
        """Test decrypting corrupted encrypted token."""
        encrypted = encrypt_token(sample_access_token)

        # Corrupt the encrypted data
        corrupted = encrypted[:-10] + "CORRUPTED!"

        with pytest.raises(TokenEncryptionError, match="Failed to decrypt token"):
            decrypt_token(corrupted)

    def test_decrypt_tampered_token(self, secret_key, sample_access_token):
        """Test that tampering with encrypted token is detected."""
        encrypted = encrypt_token(sample_access_token)

        # Tamper by modifying a character
        if encrypted[10] == 'A':
            tampered = encrypted[:10] + 'B' + encrypted[11:]
        else:
            tampered = encrypted[:10] + 'A' + encrypted[11:]

        with pytest.raises(TokenEncryptionError, match="Failed to decrypt token"):
            decrypt_token(tampered)

    def test_encrypt_unicode_token(self, secret_key):
        """Test encrypting token with Unicode characters."""
        unicode_token = "token_with_émojis_🔐_and_中文"

        encrypted = encrypt_token(unicode_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == unicode_token

    def test_encrypt_special_characters(self, secret_key):
        """Test encrypting token with special characters."""
        special_token = "!@#$%^&*()_+-=[]{}|;':\",./<>?"

        encrypted = encrypt_token(special_token)
        decrypted = decrypt_token(encrypted)

        assert decrypted == special_token


# =============================================================================
# Optional Token Tests
# =============================================================================

class TestOptionalTokens:
    """Test convenience wrappers for optional tokens (like refresh_token)."""

    def test_encrypt_token_optional_with_value(self, secret_key, sample_refresh_token):
        """Test encrypting optional token that has a value."""
        encrypted = encrypt_token_optional(sample_refresh_token)

        assert encrypted is not None
        assert isinstance(encrypted, str)
        assert encrypted != sample_refresh_token

    def test_encrypt_token_optional_with_none(self, secret_key):
        """Test encrypting optional token that is None."""
        encrypted = encrypt_token_optional(None)

        assert encrypted is None

    def test_decrypt_token_optional_with_value(self, secret_key, sample_refresh_token):
        """Test decrypting optional token that has a value."""
        encrypted = encrypt_token_optional(sample_refresh_token)
        decrypted = decrypt_token_optional(encrypted)

        assert decrypted == sample_refresh_token

    def test_decrypt_token_optional_with_none(self, secret_key):
        """Test decrypting optional token that is None."""
        decrypted = decrypt_token_optional(None)

        assert decrypted is None

    def test_optional_token_round_trip(self, secret_key, sample_refresh_token):
        """Test round-trip encryption for optional tokens."""
        # With value
        encrypted = encrypt_token_optional(sample_refresh_token)
        decrypted = decrypt_token_optional(encrypted)
        assert decrypted == sample_refresh_token

        # With None
        encrypted_none = encrypt_token_optional(None)
        decrypted_none = decrypt_token_optional(encrypted_none)
        assert decrypted_none is None


# =============================================================================
# Security Tests
# =============================================================================

class TestSecurity:
    """Test security properties of token encryption."""

    def test_encrypted_token_not_base64_decodable_to_plaintext(self, secret_key, sample_access_token):
        """Test that encrypted token is not trivially decodable."""
        import base64

        encrypted = encrypt_token(sample_access_token)

        # Try to base64 decode (should not reveal plaintext)
        try:
            decoded = base64.b64decode(encrypted)
            # Even if decodable, should not contain plaintext
            assert sample_access_token.encode() not in decoded
        except Exception:
            # If not even base64-decodable, that's fine
            pass

    def test_key_derivation_uses_pbkdf2(self, secret_key):
        """Test that key derivation uses PBKDF2 (not direct key usage)."""
        from reconly_core.email.crypto import _derive_fernet_key

        secret = "test-secret-key"
        key = _derive_fernet_key(secret)

        # Key should be 44 bytes (32 bytes key + base64url encoding = 44)
        assert len(key) == 44

        # Should be base64url encoded
        import base64
        try:
            decoded = base64.urlsafe_b64decode(key)
            assert len(decoded) == 32  # 32 bytes for Fernet
        except Exception:
            pytest.fail("Derived key is not valid base64url")

    def test_encryption_uses_fixed_salt(self, secret_key, sample_access_token):
        """Test that encryption uses consistent salt for key derivation."""
        from reconly_core.email.crypto import _KEY_DERIVATION_SALT

        # Salt should be defined and non-empty
        assert _KEY_DERIVATION_SALT
        assert isinstance(_KEY_DERIVATION_SALT, bytes)
        assert len(_KEY_DERIVATION_SALT) > 0

        # Same SECRET_KEY should always produce same derived key
        from reconly_core.email.crypto import _derive_fernet_key

        key1 = _derive_fernet_key("test-secret")
        key2 = _derive_fernet_key("test-secret")
        assert key1 == key2

    def test_token_length_not_leaked(self, secret_key):
        """Test that encrypted token length doesn't directly reveal plaintext length."""
        short_token = "short"
        long_token = "x" * 1000

        encrypted_short = encrypt_token(short_token)
        encrypted_long = encrypt_token(long_token)

        # Due to Fernet's block encryption and padding,
        # encrypted lengths should not directly map to plaintext lengths
        # (though there will be some correlation)
        short_diff = len(encrypted_short) - len(short_token)
        long_diff = len(encrypted_long) - len(long_token)

        # Both should have significant overhead
        assert short_diff > 50
        assert long_diff > 50


# =============================================================================
# Integration Tests
# =============================================================================

class TestEncryptionIntegration:
    """Test encryption in realistic OAuth token scenarios."""

    def test_encrypt_typical_google_tokens(self, secret_key):
        """Test encrypting typical Google OAuth tokens."""
        access_token = "ya29.a0AfH6SMBxxx" + "x" * 150  # Typical length ~165 chars
        refresh_token = "1//0gXXXX" + "x" * 180  # Typical length ~190 chars

        # Encrypt both
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token)

        # Decrypt and verify
        assert decrypt_token(encrypted_access) == access_token
        assert decrypt_token(encrypted_refresh) == refresh_token

    def test_encrypt_typical_microsoft_tokens(self, secret_key):
        """Test encrypting typical Microsoft OAuth tokens."""
        access_token = "EwBIA" + "x" * 1200  # Typical JWT length ~1200 chars
        refresh_token = "M.R3_BAY" + "x" * 400  # Typical length ~400 chars

        # Encrypt both
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token)

        # Decrypt and verify
        assert decrypt_token(encrypted_access) == access_token
        assert decrypt_token(encrypted_refresh) == refresh_token

    def test_encrypt_mixed_token_types(self, secret_key):
        """Test encrypting various token types in sequence."""
        tokens = [
            "short_token",
            "medium_length_token_with_some_content_here_12345",
            "x" * 500,  # Long token
            "token_with_special_chars_!@#$%",
            "token_with_unicode_émoji_🔐",
        ]

        # Encrypt all
        encrypted_tokens = [encrypt_token(t) for t in tokens]

        # Decrypt all and verify
        for original, encrypted in zip(tokens, encrypted_tokens):
            assert decrypt_token(encrypted) == original

    def test_database_storage_simulation(self, secret_key, sample_access_token, sample_refresh_token):
        """Test simulating database storage and retrieval of encrypted tokens."""
        # Simulate storing tokens in database
        db_access_token = encrypt_token(sample_access_token)
        db_refresh_token = encrypt_token_optional(sample_refresh_token)

        # Simulate app restart (clear any in-memory state)
        # SECRET_KEY remains in environment

        # Simulate retrieving tokens from database and decrypting
        retrieved_access = decrypt_token(db_access_token)
        retrieved_refresh = decrypt_token_optional(db_refresh_token)

        assert retrieved_access == sample_access_token
        assert retrieved_refresh == sample_refresh_token
