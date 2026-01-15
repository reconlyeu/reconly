"""OAuth2 state management for email provider authentication.

This module handles OAuth2 state parameter generation and validation,
including PKCE (Proof Key for Code Exchange) for enhanced security.
"""
import base64
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Tuple

from cryptography.fernet import Fernet, InvalidToken

from reconly_core.email.crypto import _get_secret_key

logger = logging.getLogger(__name__)

# State expiration time in seconds (10 minutes)
STATE_EXPIRATION_SECONDS = 600


class OAuthStateError(Exception):
    """Raised when OAuth state validation fails."""
    pass


@dataclass
class OAuthState:
    """Represents OAuth2 state data.

    Attributes:
        source_id: The source ID this OAuth flow is for
        provider: The OAuth provider (gmail, outlook)
        code_verifier: PKCE code verifier for code exchange
        timestamp: Unix timestamp when state was created
        nonce: Random nonce for additional security
    """
    source_id: int
    provider: str
    code_verifier: str
    timestamp: float
    nonce: str

    def is_expired(self) -> bool:
        """Check if this state has expired."""
        return time.time() - self.timestamp > STATE_EXPIRATION_SECONDS


def generate_pkce_pair() -> Tuple[str, str]:
    """Generate a PKCE code verifier and challenge pair.

    PKCE (Proof Key for Code Exchange) is used to prevent authorization
    code interception attacks in OAuth2 flows.

    Returns:
        Tuple of (code_verifier, code_challenge)
        - code_verifier: Random 43-128 character string sent during token exchange
        - code_challenge: SHA256 hash of verifier sent during authorization
    """
    # Generate a random 32-byte code verifier (will be 43 chars base64url encoded)
    code_verifier = secrets.token_urlsafe(32)

    # Create code challenge using S256 method (SHA256 + base64url)
    verifier_bytes = code_verifier.encode("ascii")
    challenge_bytes = hashlib.sha256(verifier_bytes).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


def _get_state_fernet() -> Fernet:
    """Get Fernet instance for state encryption.

    Uses a different salt than token encryption to isolate keys.
    """
    secret_key = _get_secret_key()
    # Use a different salt for state encryption
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"reconly-oauth-state-v1",
        iterations=100000,
    )
    key = kdf.derive(secret_key.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(key))


def create_oauth_state(source_id: int, provider: str) -> Tuple[str, str, str]:
    """Create an encrypted OAuth state parameter with PKCE.

    The state parameter is encrypted and contains:
    - source_id: Which source this OAuth flow is for
    - provider: gmail or outlook
    - code_verifier: PKCE verifier for token exchange
    - timestamp: For expiration checking
    - nonce: Additional randomness

    Args:
        source_id: The source ID to associate with this OAuth flow
        provider: The OAuth provider (gmail, outlook)

    Returns:
        Tuple of (encrypted_state, code_verifier, code_challenge)
        - encrypted_state: URL-safe encrypted state to pass to OAuth provider
        - code_verifier: Keep this for token exchange
        - code_challenge: Send this with authorization request

    Raises:
        OAuthStateError: If state creation fails
    """
    try:
        code_verifier, code_challenge = generate_pkce_pair()
        nonce = secrets.token_urlsafe(16)

        state_data = OAuthState(
            source_id=source_id,
            provider=provider,
            code_verifier=code_verifier,
            timestamp=time.time(),
            nonce=nonce,
        )

        # Serialize to JSON
        state_json = json.dumps({
            "source_id": state_data.source_id,
            "provider": state_data.provider,
            "code_verifier": state_data.code_verifier,
            "timestamp": state_data.timestamp,
            "nonce": state_data.nonce,
        })

        # Encrypt state
        fernet = _get_state_fernet()
        encrypted_state = fernet.encrypt(state_json.encode("utf-8"))
        # Make URL-safe
        state_param = base64.urlsafe_b64encode(encrypted_state).decode("ascii")

        return state_param, code_verifier, code_challenge

    except Exception as e:
        logger.error(f"Failed to create OAuth state: {e}")
        raise OAuthStateError(f"Failed to create OAuth state: {e}") from e


def validate_oauth_state(state_param: str) -> OAuthState:
    """Validate and decrypt an OAuth state parameter.

    Args:
        state_param: The encrypted state parameter from OAuth callback

    Returns:
        OAuthState with the decrypted state data

    Raises:
        OAuthStateError: If state is invalid, expired, or tampered with
    """
    if not state_param:
        raise OAuthStateError("Missing state parameter")

    try:
        # Decode from URL-safe base64
        encrypted_state = base64.urlsafe_b64decode(state_param.encode("ascii"))

        # Decrypt state
        fernet = _get_state_fernet()
        state_json = fernet.decrypt(encrypted_state).decode("utf-8")

        # Parse JSON
        state_data = json.loads(state_json)

        state = OAuthState(
            source_id=state_data["source_id"],
            provider=state_data["provider"],
            code_verifier=state_data["code_verifier"],
            timestamp=state_data["timestamp"],
            nonce=state_data["nonce"],
        )

        # Check expiration
        if state.is_expired():
            raise OAuthStateError("OAuth state has expired. Please try again.")

        return state

    except InvalidToken:
        logger.warning("OAuth state validation failed: invalid token")
        raise OAuthStateError("Invalid or tampered state parameter")
    except json.JSONDecodeError:
        logger.warning("OAuth state validation failed: invalid JSON")
        raise OAuthStateError("Corrupted state parameter")
    except KeyError as e:
        logger.warning(f"OAuth state validation failed: missing key {e}")
        raise OAuthStateError("Incomplete state parameter")
    except OAuthStateError:
        raise
    except Exception as e:
        logger.error(f"OAuth state validation failed: {e}")
        raise OAuthStateError(f"Failed to validate OAuth state: {e}") from e


def get_redirect_uri(base_url: str) -> str:
    """Build the OAuth callback redirect URI.

    Args:
        base_url: The application base URL (e.g., "http://localhost:8000")

    Returns:
        Full redirect URI for OAuth callbacks
    """
    # Ensure no trailing slash
    base_url = base_url.rstrip("/")
    return f"{base_url}/api/v1/auth/oauth/callback"
