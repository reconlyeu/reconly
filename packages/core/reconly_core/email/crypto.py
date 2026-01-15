"""Cryptographic utilities for OAuth token encryption.

This module provides Fernet symmetric encryption for securely storing
OAuth2 access and refresh tokens in the database.

The encryption key is derived from the SECRET_KEY environment variable
using PBKDF2 key derivation to ensure a valid 32-byte Fernet key.
"""
import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Salt for key derivation (fixed value for consistency)
# This is not a secret - it just adds uniqueness to the derivation
_KEY_DERIVATION_SALT = b"reconly-oauth-token-encryption-v1"


class TokenEncryptionError(Exception):
    """Raised when token encryption or decryption fails."""
    pass


def _get_secret_key() -> str:
    """Get the SECRET_KEY from environment.

    Returns:
        The SECRET_KEY value

    Raises:
        TokenEncryptionError: If SECRET_KEY is not set
    """
    secret_key = os.environ.get("SECRET_KEY", "")
    if not secret_key:
        raise TokenEncryptionError(
            "SECRET_KEY environment variable is not set. "
            "OAuth token encryption requires a secure SECRET_KEY."
        )
    return secret_key


def _derive_fernet_key(secret_key: str) -> bytes:
    """Derive a valid 32-byte Fernet key from the SECRET_KEY.

    Uses PBKDF2 key derivation to ensure the key is exactly 32 bytes
    and suitable for Fernet encryption.

    Args:
        secret_key: The application SECRET_KEY

    Returns:
        A 32-byte key suitable for Fernet encryption
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KEY_DERIVATION_SALT,
        iterations=100000,
    )
    key = kdf.derive(secret_key.encode("utf-8"))
    return base64.urlsafe_b64encode(key)


def _get_fernet() -> Fernet:
    """Get a Fernet instance configured with the derived key.

    Returns:
        Fernet instance for encryption/decryption

    Raises:
        TokenEncryptionError: If key derivation fails
    """
    try:
        secret_key = _get_secret_key()
        fernet_key = _derive_fernet_key(secret_key)
        return Fernet(fernet_key)
    except TokenEncryptionError:
        raise
    except Exception as e:
        raise TokenEncryptionError(f"Failed to initialize encryption: {e}") from e


def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token for secure storage.

    Args:
        token: The plaintext OAuth token to encrypt

    Returns:
        Base64-encoded encrypted token string

    Raises:
        TokenEncryptionError: If encryption fails
    """
    if not token:
        raise TokenEncryptionError("Cannot encrypt empty token")

    try:
        fernet = _get_fernet()
        encrypted = fernet.encrypt(token.encode("utf-8"))
        return encrypted.decode("utf-8")
    except TokenEncryptionError:
        raise
    except Exception as e:
        logger.error(f"Token encryption failed: {e}")
        raise TokenEncryptionError(f"Failed to encrypt token: {e}") from e


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt an OAuth token from storage.

    Args:
        encrypted_token: The encrypted token string from database

    Returns:
        The decrypted plaintext token

    Raises:
        TokenEncryptionError: If decryption fails (invalid key or corrupted data)
    """
    if not encrypted_token:
        raise TokenEncryptionError("Cannot decrypt empty token")

    try:
        fernet = _get_fernet()
        decrypted = fernet.decrypt(encrypted_token.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.error("Token decryption failed: invalid token or key mismatch")
        raise TokenEncryptionError(
            "Failed to decrypt token. This may indicate the SECRET_KEY has changed "
            "or the token data is corrupted."
        )
    except TokenEncryptionError:
        raise
    except Exception as e:
        logger.error(f"Token decryption failed: {e}")
        raise TokenEncryptionError(f"Failed to decrypt token: {e}") from e


def encrypt_token_optional(token: Optional[str]) -> Optional[str]:
    """Encrypt an OAuth token, handling None values.

    Convenience wrapper for optional tokens like refresh_token.

    Args:
        token: The plaintext token or None

    Returns:
        Encrypted token string or None if input was None
    """
    if token is None:
        return None
    return encrypt_token(token)


def decrypt_token_optional(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt an OAuth token, handling None values.

    Convenience wrapper for optional tokens like refresh_token.

    Args:
        encrypted_token: The encrypted token or None

    Returns:
        Decrypted token string or None if input was None
    """
    if encrypted_token is None:
        return None
    return decrypt_token(encrypted_token)
