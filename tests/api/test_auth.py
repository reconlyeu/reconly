"""Tests for authentication API routes and middleware."""
import base64
import pytest
from unittest.mock import patch

from reconly_api.auth.password import (
    timing_safe_compare,
    create_session_token,
    verify_session_token,
    _failed_attempts,
    _is_rate_limited,
    _record_failed_attempt,
    _clear_failed_attempts,
    SESSION_COOKIE_NAME,
)


class TestTimingSafeCompare:
    """Tests for timing-safe password comparison."""

    def test_equal_strings(self):
        """Equal strings should return True."""
        assert timing_safe_compare("password123", "password123") is True

    def test_unequal_strings(self):
        """Different strings should return False."""
        assert timing_safe_compare("password123", "password456") is False

    def test_empty_strings(self):
        """Empty strings should match."""
        assert timing_safe_compare("", "") is True

    def test_empty_vs_nonempty(self):
        """Empty vs non-empty should return False."""
        assert timing_safe_compare("", "password") is False
        assert timing_safe_compare("password", "") is False


class TestSessionTokens:
    """Tests for session token creation and verification."""

    def test_create_and_verify_token(self):
        """Created token should verify correctly."""
        from datetime import datetime, timedelta

        secret = "test-secret-key"
        expires_at = datetime.utcnow() + timedelta(hours=1)

        token = create_session_token(secret, expires_at)
        assert verify_session_token(token, secret) is True

    def test_expired_token_fails(self):
        """Expired token should not verify."""
        from datetime import datetime, timedelta

        secret = "test-secret-key"
        expires_at = datetime.utcnow() - timedelta(hours=1)  # Already expired

        token = create_session_token(secret, expires_at)
        assert verify_session_token(token, secret) is False

    def test_wrong_secret_fails(self):
        """Token with wrong secret should not verify."""
        from datetime import datetime, timedelta

        secret = "correct-secret"
        wrong_secret = "wrong-secret"
        expires_at = datetime.utcnow() + timedelta(hours=1)

        token = create_session_token(secret, expires_at)
        assert verify_session_token(token, wrong_secret) is False

    def test_tampered_token_fails(self):
        """Tampered token should not verify."""
        from datetime import datetime, timedelta

        secret = "test-secret-key"
        expires_at = datetime.utcnow() + timedelta(hours=1)

        token = create_session_token(secret, expires_at)
        # Tamper with the payload
        parts = token.split('.')
        tampered = "XXX" + parts[0][3:] + "." + parts[1]
        assert verify_session_token(tampered, secret) is False

    def test_invalid_token_format_fails(self):
        """Invalid token format should not verify."""
        secret = "test-secret-key"

        assert verify_session_token("invalid", secret) is False
        assert verify_session_token("", secret) is False
        assert verify_session_token("no.dots.here.at.all", secret) is False


class TestRateLimiting:
    """Tests for login rate limiting."""

    def setup_method(self):
        """Clear rate limit state before each test."""
        _failed_attempts.clear()

    def test_not_rate_limited_initially(self):
        """Fresh IP should not be rate limited."""
        assert _is_rate_limited("192.168.1.1") is False

    def test_rate_limited_after_max_attempts(self):
        """IP should be rate limited after 5 failed attempts."""
        ip = "192.168.1.2"

        # Record 5 failed attempts
        for _ in range(5):
            _record_failed_attempt(ip)

        assert _is_rate_limited(ip) is True

    def test_not_rate_limited_before_max(self):
        """IP should not be rate limited before 5 attempts."""
        ip = "192.168.1.3"

        # Record 4 failed attempts
        for _ in range(4):
            _record_failed_attempt(ip)

        assert _is_rate_limited(ip) is False

    def test_clear_failed_attempts(self):
        """Clearing failed attempts should reset rate limiting."""
        ip = "192.168.1.4"

        # Rate limit the IP
        for _ in range(5):
            _record_failed_attempt(ip)
        assert _is_rate_limited(ip) is True

        # Clear and verify
        _clear_failed_attempts(ip)
        assert _is_rate_limited(ip) is False


@pytest.mark.api
class TestAuthRoutesNoPassword:
    """Tests for auth routes when no password is configured (default)."""

    def test_config_returns_auth_not_required(self, client):
        """GET /api/config should return auth_required: false when no password."""
        response = client.get("/api/v1/auth/config/")
        assert response.status_code == 200
        data = response.json()
        assert data["auth_required"] is False
        assert data["edition"] == "oss"

    def test_login_succeeds_without_password(self, client):
        """Login should succeed when no password is configured."""
        response = client.post("/api/v1/auth/login/", json={"password": "anything"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Authentication not required"

    def test_logout_always_succeeds(self, client):
        """Logout should always succeed."""
        response = client.post("/api/v1/auth/logout/")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_protected_route_accessible(self, client, sample_source):
        """Protected routes should be accessible without password configured."""
        # Use sources endpoint (no trailing slash matches route definition)
        response = client.get("/api/v1/sources")
        assert response.status_code == 200


@pytest.mark.api
class TestAuthRoutesWithPassword:
    """Tests for auth routes when password is configured."""

    @pytest.fixture(autouse=True)
    def setup_password(self, monkeypatch):
        """Configure a test password."""
        monkeypatch.setenv("SKIMBERRY_AUTH_PASSWORD", "test-password-123")
        # Clear rate limiting state
        _failed_attempts.clear()

    def test_config_returns_auth_required(self, client, monkeypatch):
        """GET /api/config should return auth_required: true when password set."""
        # Need to patch settings since it's loaded at import time
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            # Patch the settings object directly
            settings.reconly_auth_password = "test-password-123"

            response = client.get("/api/v1/auth/config/")
            assert response.status_code == 200
            data = response.json()
            assert data["auth_required"] is True
        finally:
            settings.reconly_auth_password = original_password

    def test_login_with_correct_password(self, client, monkeypatch):
        """Login with correct password should succeed and set cookie."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            response = client.post("/api/v1/auth/login/", json={"password": "test-password-123"})
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Login successful"

            # Check that session cookie was set
            assert SESSION_COOKIE_NAME in response.cookies
        finally:
            settings.reconly_auth_password = original_password

    def test_login_with_wrong_password(self, client, monkeypatch):
        """Login with wrong password should fail."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            response = client.post("/api/v1/auth/login/", json={"password": "wrong-password"})
            assert response.status_code == 401
            assert "Invalid password" in response.json()["detail"]
        finally:
            settings.reconly_auth_password = original_password

    def test_protected_route_requires_auth(self, client, monkeypatch, sample_source):
        """Protected routes should require auth when password is configured."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            response = client.get("/api/v1/sources")
            assert response.status_code == 401
        finally:
            settings.reconly_auth_password = original_password

    def test_protected_route_with_basic_auth(self, client, monkeypatch, sample_source):
        """Protected routes should work with Basic Auth."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            # Create Basic Auth header (empty username, password as value)
            credentials = base64.b64encode(b":test-password-123").decode()
            headers = {"Authorization": f"Basic {credentials}"}

            response = client.get("/api/v1/sources", headers=headers)
            assert response.status_code == 200
        finally:
            settings.reconly_auth_password = original_password

    def test_protected_route_with_session_cookie(self, client, monkeypatch, sample_source):
        """Protected routes should work with session cookie from login."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            # First login to get session cookie
            login_response = client.post("/api/v1/auth/login/", json={"password": "test-password-123"})
            assert login_response.status_code == 200

            # Use the cookie for subsequent requests
            response = client.get("/api/v1/sources")
            assert response.status_code == 200
        finally:
            settings.reconly_auth_password = original_password

    def test_rate_limiting_on_failed_login(self, client, monkeypatch):
        """Login should be rate limited after 5 failed attempts."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password
        _failed_attempts.clear()

        try:
            settings.reconly_auth_password = "test-password-123"

            # Make 5 failed login attempts
            for _ in range(5):
                response = client.post("/api/v1/auth/login/", json={"password": "wrong"})
                assert response.status_code == 401

            # 6th attempt should be rate limited
            response = client.post("/api/v1/auth/login/", json={"password": "wrong"})
            assert response.status_code == 429
            assert "Too many" in response.json()["detail"]
        finally:
            settings.reconly_auth_password = original_password
            _failed_attempts.clear()

    def test_health_endpoint_always_accessible(self, client, monkeypatch):
        """Health endpoint should not require auth."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            response = client.get("/health")
            assert response.status_code == 200
        finally:
            settings.reconly_auth_password = original_password

    def test_docs_endpoint_always_accessible(self, client, monkeypatch):
        """Docs endpoint should not require auth."""
        from reconly_api.config import settings
        original_password = settings.reconly_auth_password

        try:
            settings.reconly_auth_password = "test-password-123"

            response = client.get("/docs")
            assert response.status_code == 200
        finally:
            settings.reconly_auth_password = original_password
