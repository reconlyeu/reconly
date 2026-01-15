"""Integration tests for OAuth2 flows (Gmail and Outlook).

Tests OAuth state management, URL generation, token exchange, and token refresh
for both Gmail and Outlook providers. All external OAuth endpoints are mocked.
"""
import base64
import hashlib
import json
import os
import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import requests

from reconly_core.email.gmail import (
    GMAIL_AUTH_URL,
    GMAIL_SCOPES,
    GMAIL_TOKEN_URL,
    GmailOAuthError,
    GmailTokens,
    exchange_gmail_code,
    generate_gmail_auth_url,
    get_gmail_client_credentials,
    refresh_gmail_token,
    revoke_gmail_token,
)
from reconly_core.email.oauth import (
    OAuthState,
    OAuthStateError,
    create_oauth_state,
    generate_pkce_pair,
    get_redirect_uri,
    validate_oauth_state,
)
from reconly_core.email.outlook import (
    MICROSOFT_AUTH_URL,
    MICROSOFT_TOKEN_URL,
    OUTLOOK_SCOPES,
    OutlookOAuthError,
    OutlookTokens,
    exchange_outlook_code,
    generate_outlook_auth_url,
    get_outlook_client_credentials,
    refresh_outlook_token,
    revoke_outlook_token,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def gmail_env_credentials():
    """Set up Gmail OAuth credentials in environment."""
    old_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    old_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    os.environ["GOOGLE_CLIENT_ID"] = "test_gmail_client_id"
    os.environ["GOOGLE_CLIENT_SECRET"] = "test_gmail_client_secret"

    yield

    # Restore original values
    if old_client_id:
        os.environ["GOOGLE_CLIENT_ID"] = old_client_id
    else:
        os.environ.pop("GOOGLE_CLIENT_ID", None)

    if old_client_secret:
        os.environ["GOOGLE_CLIENT_SECRET"] = old_client_secret
    else:
        os.environ.pop("GOOGLE_CLIENT_SECRET", None)


@pytest.fixture
def outlook_env_credentials():
    """Set up Outlook OAuth credentials in environment."""
    old_client_id = os.environ.get("MICROSOFT_CLIENT_ID")
    old_client_secret = os.environ.get("MICROSOFT_CLIENT_SECRET")

    os.environ["MICROSOFT_CLIENT_ID"] = "test_outlook_client_id"
    os.environ["MICROSOFT_CLIENT_SECRET"] = "test_outlook_client_secret"

    yield

    # Restore original values
    if old_client_id:
        os.environ["MICROSOFT_CLIENT_ID"] = old_client_id
    else:
        os.environ.pop("MICROSOFT_CLIENT_ID", None)

    if old_client_secret:
        os.environ["MICROSOFT_CLIENT_SECRET"] = old_client_secret
    else:
        os.environ.pop("MICROSOFT_CLIENT_SECRET", None)


@pytest.fixture
def secret_key():
    """Set up SECRET_KEY for state encryption."""
    old_secret = os.environ.get("SECRET_KEY")
    os.environ["SECRET_KEY"] = "test-secret-key-for-oauth-state-encryption"

    yield

    if old_secret:
        os.environ["SECRET_KEY"] = old_secret
    else:
        os.environ.pop("SECRET_KEY", None)


@pytest.fixture
def mock_gmail_token_response():
    """Mock successful Gmail token exchange response."""
    return {
        "access_token": "ya29.test_gmail_access_token",
        "refresh_token": "1//test_gmail_refresh_token",
        "expires_in": 3600,
        "scope": " ".join(GMAIL_SCOPES),
        "token_type": "Bearer",
    }


@pytest.fixture
def mock_outlook_token_response():
    """Mock successful Outlook token exchange response."""
    return {
        "access_token": "EwBIA.test_outlook_access_token",
        "refresh_token": "M.R3.test_outlook_refresh_token",
        "expires_in": 3600,
        "scope": " ".join(OUTLOOK_SCOPES),
        "token_type": "Bearer",
    }


# =============================================================================
# PKCE Tests
# =============================================================================

class TestPKCE:
    """Test PKCE (Proof Key for Code Exchange) implementation."""

    def test_generate_pkce_pair(self):
        """Test PKCE code verifier and challenge generation."""
        verifier, challenge = generate_pkce_pair()

        # Verifier should be 43 characters (base64url encoded 32 bytes)
        assert len(verifier) == 43
        assert verifier.replace("-", "").replace("_", "").isalnum()

        # Challenge should be base64url encoded SHA256 of verifier
        expected_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        assert challenge == expected_challenge

    def test_pkce_pairs_are_unique(self):
        """Test that PKCE pairs are randomly generated."""
        verifier1, challenge1 = generate_pkce_pair()
        verifier2, challenge2 = generate_pkce_pair()

        assert verifier1 != verifier2
        assert challenge1 != challenge2

    def test_pkce_challenge_verifiable(self):
        """Test that PKCE challenge can be verified from verifier."""
        verifier, challenge = generate_pkce_pair()

        # Compute challenge from verifier
        computed_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")

        assert computed_challenge == challenge


# =============================================================================
# OAuth State Management Tests
# =============================================================================

class TestOAuthState:
    """Test OAuth state parameter creation and validation."""

    def test_create_oauth_state(self, secret_key):
        """Test creating encrypted OAuth state parameter."""
        source_id = 42
        provider = "gmail"

        state_param, code_verifier, code_challenge = create_oauth_state(source_id, provider)

        # State should be URL-safe base64 encoded string
        assert isinstance(state_param, str)
        assert len(state_param) > 50  # Encrypted payload should be substantial

        # PKCE values should be returned
        assert len(code_verifier) == 43
        assert len(code_challenge) > 40

    def test_validate_oauth_state(self, secret_key):
        """Test validating and decrypting OAuth state parameter."""
        source_id = 42
        provider = "gmail"

        state_param, code_verifier, code_challenge = create_oauth_state(source_id, provider)

        # Validate state
        state = validate_oauth_state(state_param)

        assert state.source_id == source_id
        assert state.provider == provider
        assert state.code_verifier == code_verifier
        assert isinstance(state.timestamp, float)
        assert isinstance(state.nonce, str)
        assert not state.is_expired()

    def test_validate_expired_state(self, secret_key):
        """Test that expired state is rejected."""
        state_param, _, _ = create_oauth_state(42, "gmail")

        # Decode and modify timestamp to be old
        encrypted_state = base64.urlsafe_b64decode(state_param.encode("ascii"))

        from reconly_core.email.oauth import _get_state_fernet
        fernet = _get_state_fernet()
        state_json = fernet.decrypt(encrypted_state).decode("utf-8")
        state_data = json.loads(state_json)

        # Set timestamp to 11 minutes ago (should expire after 10 minutes)
        state_data["timestamp"] = time.time() - 660

        # Re-encrypt with old timestamp
        modified_json = json.dumps(state_data)
        modified_encrypted = fernet.encrypt(modified_json.encode("utf-8"))
        modified_param = base64.urlsafe_b64encode(modified_encrypted).decode("ascii")

        # Validation should fail
        with pytest.raises(OAuthStateError, match="expired"):
            validate_oauth_state(modified_param)

    def test_validate_tampered_state(self, secret_key):
        """Test that tampered state is rejected."""
        state_param, _, _ = create_oauth_state(42, "gmail")

        # Tamper with the state parameter
        tampered_param = state_param[:-10] + "TAMPERED!!"

        # Should raise error (message may vary based on how tampering broke it)
        with pytest.raises(OAuthStateError):
            validate_oauth_state(tampered_param)

    def test_validate_missing_state(self, secret_key):
        """Test that missing state parameter is rejected."""
        with pytest.raises(OAuthStateError, match="Missing state"):
            validate_oauth_state("")

    def test_get_redirect_uri(self):
        """Test OAuth redirect URI generation."""
        base_url = "http://localhost:8000"
        redirect_uri = get_redirect_uri(base_url)

        assert redirect_uri == "http://localhost:8000/api/v1/auth/oauth/callback"

        # Should handle trailing slash
        redirect_uri2 = get_redirect_uri("http://localhost:8000/")
        assert redirect_uri2 == redirect_uri


# =============================================================================
# Gmail OAuth Tests
# =============================================================================

class TestGmailOAuth:
    """Test Gmail OAuth2 flow."""

    def test_get_gmail_credentials(self, gmail_env_credentials):
        """Test retrieving Gmail OAuth credentials from environment."""
        client_id, client_secret = get_gmail_client_credentials()

        assert client_id == "test_gmail_client_id"
        assert client_secret == "test_gmail_client_secret"

    def test_get_gmail_credentials_missing(self):
        """Test error when Gmail credentials are not configured."""
        # Temporarily remove credentials
        old_id = os.environ.pop("GOOGLE_CLIENT_ID", None)
        old_secret = os.environ.pop("GOOGLE_CLIENT_SECRET", None)

        try:
            with pytest.raises(GmailOAuthError, match="not configured"):
                get_gmail_client_credentials()
        finally:
            if old_id:
                os.environ["GOOGLE_CLIENT_ID"] = old_id
            if old_secret:
                os.environ["GOOGLE_CLIENT_SECRET"] = old_secret

    def test_generate_gmail_auth_url(self, gmail_env_credentials, secret_key):
        """Test Gmail OAuth authorization URL generation."""
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        state, _, code_challenge = create_oauth_state(42, "gmail")

        auth_url = generate_gmail_auth_url(redirect_uri, state, code_challenge)

        # Verify URL structure (redirect_uri will be URL-encoded)
        from urllib.parse import unquote

        assert auth_url.startswith(GMAIL_AUTH_URL)
        assert "client_id=test_gmail_client_id" in auth_url
        # URL parameters are encoded, so check for encoded version
        assert redirect_uri in unquote(auth_url)
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert f"code_challenge={code_challenge}" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "access_type=offline" in auth_url
        assert "prompt=consent" in auth_url

        # Verify scopes (will be URL-encoded in the URL)
        decoded_url = unquote(auth_url)
        for scope in GMAIL_SCOPES:
            assert scope in decoded_url

    def test_exchange_gmail_code_success(self, gmail_env_credentials, mock_gmail_token_response):
        """Test successful Gmail authorization code exchange."""
        code = "test_authorization_code"
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        code_verifier = "test_code_verifier_43_characters_long_xyz123"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_gmail_token_response
            mock_post.return_value = mock_response

            tokens = exchange_gmail_code(code, redirect_uri, code_verifier)

            # Verify request
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == GMAIL_TOKEN_URL
            assert call_args[1]["data"]["code"] == code
            assert call_args[1]["data"]["code_verifier"] == code_verifier
            assert call_args[1]["data"]["grant_type"] == "authorization_code"
            assert call_args[1]["data"]["redirect_uri"] == redirect_uri

            # Verify tokens
            assert isinstance(tokens, GmailTokens)
            assert tokens.access_token == "ya29.test_gmail_access_token"
            assert tokens.refresh_token == "1//test_gmail_refresh_token"
            assert tokens.expires_at > datetime.utcnow()
            assert tokens.scopes == GMAIL_SCOPES

    def test_exchange_gmail_code_failure(self, gmail_env_credentials):
        """Test Gmail code exchange failure handling."""
        code = "invalid_code"
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        code_verifier = "test_code_verifier_43_characters_long_xyz123"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_grant",
                "error_description": "Invalid authorization code"
            }
            mock_response.text = json.dumps(mock_response.json.return_value)
            mock_post.return_value = mock_response

            with pytest.raises(GmailOAuthError, match="Invalid authorization code"):
                exchange_gmail_code(code, redirect_uri, code_verifier)

    def test_exchange_gmail_code_network_error(self, gmail_env_credentials):
        """Test Gmail code exchange network error handling."""
        code = "test_code"
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        code_verifier = "test_code_verifier_43_characters_long_xyz123"

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.RequestException("Network error")

            with pytest.raises(GmailOAuthError, match="Network error"):
                exchange_gmail_code(code, redirect_uri, code_verifier)

    def test_refresh_gmail_token_success(self, gmail_env_credentials, mock_gmail_token_response):
        """Test successful Gmail token refresh."""
        refresh_token = "1//test_refresh_token"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            # Refresh response typically doesn't include new refresh token
            refresh_response = mock_gmail_token_response.copy()
            refresh_response.pop("refresh_token", None)
            mock_response.json.return_value = refresh_response
            mock_post.return_value = mock_response

            tokens = refresh_gmail_token(refresh_token)

            # Verify request
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == GMAIL_TOKEN_URL
            assert call_args[1]["data"]["refresh_token"] == refresh_token
            assert call_args[1]["data"]["grant_type"] == "refresh_token"

            # Verify tokens
            assert isinstance(tokens, GmailTokens)
            assert tokens.access_token == "ya29.test_gmail_access_token"
            # Should preserve original refresh token if not in response
            assert tokens.refresh_token == refresh_token
            assert tokens.expires_at > datetime.utcnow()

    def test_refresh_gmail_token_failure(self, gmail_env_credentials):
        """Test Gmail token refresh failure handling."""
        refresh_token = "invalid_refresh_token"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_grant",
                "error_description": "Token has been expired or revoked"
            }
            mock_response.text = json.dumps(mock_response.json.return_value)
            mock_post.return_value = mock_response

            with pytest.raises(GmailOAuthError, match="expired or revoked"):
                refresh_gmail_token(refresh_token)

    def test_revoke_gmail_token_success(self):
        """Test successful Gmail token revocation."""
        token = "test_token_to_revoke"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = revoke_gmail_token(token)

            assert result is True
            mock_post.assert_called_once()
            assert mock_post.call_args[1]["data"]["token"] == token

    def test_revoke_gmail_token_failure(self):
        """Test Gmail token revocation failure (returns False, doesn't raise)."""
        token = "test_token"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_post.return_value = mock_response

            result = revoke_gmail_token(token)

            # Revocation failures are graceful
            assert result is False


# =============================================================================
# Outlook OAuth Tests
# =============================================================================

class TestOutlookOAuth:
    """Test Outlook/Microsoft 365 OAuth2 flow."""

    def test_get_outlook_credentials(self, outlook_env_credentials):
        """Test retrieving Outlook OAuth credentials from environment."""
        client_id, client_secret = get_outlook_client_credentials()

        assert client_id == "test_outlook_client_id"
        assert client_secret == "test_outlook_client_secret"

    def test_get_outlook_credentials_missing(self):
        """Test error when Outlook credentials are not configured."""
        old_id = os.environ.pop("MICROSOFT_CLIENT_ID", None)
        old_secret = os.environ.pop("MICROSOFT_CLIENT_SECRET", None)

        try:
            with pytest.raises(OutlookOAuthError, match="not configured"):
                get_outlook_client_credentials()
        finally:
            if old_id:
                os.environ["MICROSOFT_CLIENT_ID"] = old_id
            if old_secret:
                os.environ["MICROSOFT_CLIENT_SECRET"] = old_secret

    def test_generate_outlook_auth_url(self, outlook_env_credentials, secret_key):
        """Test Outlook OAuth authorization URL generation."""
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        state, _, code_challenge = create_oauth_state(42, "outlook")

        auth_url = generate_outlook_auth_url(redirect_uri, state, code_challenge)

        # Verify URL structure (redirect_uri will be URL-encoded)
        from urllib.parse import unquote

        assert auth_url.startswith(MICROSOFT_AUTH_URL)
        assert "client_id=test_outlook_client_id" in auth_url
        # URL parameters are encoded, so check for encoded version
        assert redirect_uri in unquote(auth_url)
        assert "response_type=code" in auth_url
        assert f"state={state}" in auth_url
        assert f"code_challenge={code_challenge}" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "response_mode=query" in auth_url
        assert "prompt=consent" in auth_url

        # Verify scopes (will be URL-encoded in the URL)
        decoded_url = unquote(auth_url)
        for scope in OUTLOOK_SCOPES:
            assert scope in decoded_url

    def test_exchange_outlook_code_success(self, outlook_env_credentials, mock_outlook_token_response):
        """Test successful Outlook authorization code exchange."""
        code = "test_authorization_code"
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        code_verifier = "test_code_verifier_43_characters_long_xyz123"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_outlook_token_response
            mock_post.return_value = mock_response

            tokens = exchange_outlook_code(code, redirect_uri, code_verifier)

            # Verify request
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == MICROSOFT_TOKEN_URL
            assert call_args[1]["data"]["code"] == code
            assert call_args[1]["data"]["code_verifier"] == code_verifier
            assert call_args[1]["data"]["grant_type"] == "authorization_code"
            assert call_args[1]["data"]["redirect_uri"] == redirect_uri

            # Verify tokens
            assert isinstance(tokens, OutlookTokens)
            assert tokens.access_token == "EwBIA.test_outlook_access_token"
            assert tokens.refresh_token == "M.R3.test_outlook_refresh_token"
            assert tokens.expires_at > datetime.utcnow()
            assert tokens.scopes == OUTLOOK_SCOPES

    def test_exchange_outlook_code_failure(self, outlook_env_credentials):
        """Test Outlook code exchange failure handling."""
        code = "invalid_code"
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        code_verifier = "test_code_verifier_43_characters_long_xyz123"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_grant",
                "error_description": "The provided authorization code is invalid"
            }
            mock_response.text = json.dumps(mock_response.json.return_value)
            mock_post.return_value = mock_response

            with pytest.raises(OutlookOAuthError, match="invalid"):
                exchange_outlook_code(code, redirect_uri, code_verifier)

    def test_exchange_outlook_code_network_error(self, outlook_env_credentials):
        """Test Outlook code exchange network error handling."""
        code = "test_code"
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        code_verifier = "test_code_verifier_43_characters_long_xyz123"

        with patch("requests.post") as mock_post:
            mock_post.side_effect = requests.RequestException("Network timeout")

            with pytest.raises(OutlookOAuthError, match="Network"):
                exchange_outlook_code(code, redirect_uri, code_verifier)

    def test_refresh_outlook_token_success(self, outlook_env_credentials, mock_outlook_token_response):
        """Test successful Outlook token refresh."""
        refresh_token = "M.R3.test_refresh_token"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            # Outlook may return new refresh token
            refresh_response = mock_outlook_token_response.copy()
            refresh_response["refresh_token"] = "M.R3.new_refresh_token"
            mock_response.json.return_value = refresh_response
            mock_post.return_value = mock_response

            tokens = refresh_outlook_token(refresh_token)

            # Verify request
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == MICROSOFT_TOKEN_URL
            assert call_args[1]["data"]["refresh_token"] == refresh_token
            assert call_args[1]["data"]["grant_type"] == "refresh_token"

            # Verify tokens
            assert isinstance(tokens, OutlookTokens)
            assert tokens.access_token == "EwBIA.test_outlook_access_token"
            # Should use new refresh token if provided
            assert tokens.refresh_token == "M.R3.new_refresh_token"
            assert tokens.expires_at > datetime.utcnow()

    def test_refresh_outlook_token_failure(self, outlook_env_credentials):
        """Test Outlook token refresh failure handling."""
        refresh_token = "invalid_refresh_token"

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                "error": "invalid_grant",
                "error_description": "Refresh token has expired"
            }
            mock_response.text = json.dumps(mock_response.json.return_value)
            mock_post.return_value = mock_response

            with pytest.raises(OutlookOAuthError, match="expired"):
                refresh_outlook_token(refresh_token)

    def test_revoke_outlook_token_success(self):
        """Test Outlook token revocation (always succeeds - no API endpoint)."""
        token = "test_token_to_revoke"

        # Microsoft doesn't have a standard revocation endpoint
        result = revoke_outlook_token(token)

        # Should return True but not actually revoke (tokens expire naturally)
        assert result is True


# =============================================================================
# OAuth Flow Integration Tests
# =============================================================================

class TestOAuthFlowIntegration:
    """Test complete OAuth flows from start to finish."""

    def test_gmail_complete_flow(self, gmail_env_credentials, secret_key, mock_gmail_token_response):
        """Test complete Gmail OAuth flow: URL generation -> code exchange."""
        # Step 1: Generate authorization URL
        source_id = 123
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        state, code_verifier, code_challenge = create_oauth_state(source_id, "gmail")

        auth_url = generate_gmail_auth_url(redirect_uri, state, code_challenge)
        assert "code_challenge=" + code_challenge in auth_url
        assert "state=" + state in auth_url

        # Step 2: Simulate OAuth callback with authorization code
        authorization_code = "4/test_authorization_code_from_google"

        # Step 3: Validate state from callback
        validated_state = validate_oauth_state(state)
        assert validated_state.source_id == source_id
        assert validated_state.provider == "gmail"
        assert validated_state.code_verifier == code_verifier

        # Step 4: Exchange code for tokens
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_gmail_token_response
            mock_post.return_value = mock_response

            tokens = exchange_gmail_code(
                authorization_code,
                redirect_uri,
                validated_state.code_verifier
            )

            assert tokens.access_token == "ya29.test_gmail_access_token"
            assert tokens.refresh_token == "1//test_gmail_refresh_token"

    def test_outlook_complete_flow(self, outlook_env_credentials, secret_key, mock_outlook_token_response):
        """Test complete Outlook OAuth flow: URL generation -> code exchange."""
        # Step 1: Generate authorization URL
        source_id = 456
        redirect_uri = "http://localhost:8000/api/v1/auth/oauth/callback"
        state, code_verifier, code_challenge = create_oauth_state(source_id, "outlook")

        auth_url = generate_outlook_auth_url(redirect_uri, state, code_challenge)
        assert "code_challenge=" + code_challenge in auth_url
        assert "state=" + state in auth_url

        # Step 2: Simulate OAuth callback with authorization code
        authorization_code = "M.test_authorization_code_from_microsoft"

        # Step 3: Validate state from callback
        validated_state = validate_oauth_state(state)
        assert validated_state.source_id == source_id
        assert validated_state.provider == "outlook"
        assert validated_state.code_verifier == code_verifier

        # Step 4: Exchange code for tokens
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_outlook_token_response
            mock_post.return_value = mock_response

            tokens = exchange_outlook_code(
                authorization_code,
                redirect_uri,
                validated_state.code_verifier
            )

            assert tokens.access_token == "EwBIA.test_outlook_access_token"
            assert tokens.refresh_token == "M.R3.test_outlook_refresh_token"

    def test_token_refresh_flow(self, gmail_env_credentials, mock_gmail_token_response):
        """Test token refresh flow when access token expires."""
        # Initial tokens (expired access token)
        old_refresh_token = "1//old_refresh_token"

        # Refresh the token
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            # New access token, keep refresh token
            refresh_response = {
                "access_token": "ya29.new_access_token",
                "expires_in": 3600,
                "scope": " ".join(GMAIL_SCOPES),
                "token_type": "Bearer",
            }
            mock_response.json.return_value = refresh_response
            mock_post.return_value = mock_response

            new_tokens = refresh_gmail_token(old_refresh_token)

            # Should have new access token
            assert new_tokens.access_token == "ya29.new_access_token"
            # Should preserve refresh token
            assert new_tokens.refresh_token == old_refresh_token
            # Should have new expiration
            assert new_tokens.expires_at > datetime.utcnow()
