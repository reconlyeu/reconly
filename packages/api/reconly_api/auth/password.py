"""Simple password authentication for OSS deployments.

This module provides optional password protection for Reconly OSS.
When RECONLY_AUTH_PASSWORD is set, all API routes (except health, config, and auth)
require authentication via either:
1. Session cookie (from /api/auth/login)
2. HTTP Basic Auth (for CLI/scripts)

Design decisions (from design.md):
- Decision 6: Signed cookies (JWT-like) for session storage - stateless, survives restarts
- Decision 7: Support both cookies and HTTP Basic Auth
- Decision 8: In-memory rate limiting - 5 failed attempts per IP per minute
- Decision 9: Protect all routes except health, config, and auth endpoints
"""
import base64
import hashlib
import hmac
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable

from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel

from reconly_api.config import settings


# Session cookie configuration
SESSION_COOKIE_NAME = "reconly_session"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


class LoginRequest(BaseModel):
    """Request body for login endpoint."""
    password: str


class LoginResponse(BaseModel):
    """Response body for login endpoint."""
    success: bool
    message: str


class ConfigResponse(BaseModel):
    """Response body for config endpoint."""
    auth_required: bool
    edition: str


# In-memory rate limiting for login attempts
# Key: IP address, Value: list of timestamps of failed attempts
_failed_attempts: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_ATTEMPTS = 5


def _cleanup_old_attempts(ip: str) -> None:
    """Remove failed attempts older than the rate limit window."""
    cutoff = time.time() - RATE_LIMIT_WINDOW
    _failed_attempts[ip] = [ts for ts in _failed_attempts[ip] if ts > cutoff]


def _is_rate_limited(ip: str) -> bool:
    """Check if an IP is rate limited."""
    _cleanup_old_attempts(ip)
    return len(_failed_attempts[ip]) >= RATE_LIMIT_MAX_ATTEMPTS


def _record_failed_attempt(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    _cleanup_old_attempts(ip)
    _failed_attempts[ip].append(time.time())


def _clear_failed_attempts(ip: str) -> None:
    """Clear failed attempts after successful login."""
    _failed_attempts.pop(ip, None)


def timing_safe_compare(a: str, b: str) -> bool:
    """
    Compare two strings using constant-time comparison.

    Prevents timing attacks by ensuring the comparison takes the same
    amount of time regardless of where the strings differ.
    """
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def create_session_token(secret_key: str, expires_at: datetime) -> str:
    """
    Create a signed session token (similar to JWT but simpler).

    Format: base64(payload).base64(signature)
    Payload: {"exp": unix_timestamp}
    """
    payload = {
        "exp": int(expires_at.timestamp()),
        "iat": int(datetime.utcnow().timestamp()),
    }
    payload_json = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

    # Create HMAC signature
    signature = hmac.new(
        secret_key.encode('utf-8'),
        payload_b64.encode('utf-8'),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode()

    return f"{payload_b64}.{signature_b64}"


def verify_session_token(token: str, secret_key: str) -> bool:
    """
    Verify a session token's signature and expiration.

    Returns True if the token is valid and not expired.
    """
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return False

        payload_b64, signature_b64 = parts

        # Verify signature
        expected_signature = hmac.new(
            secret_key.encode('utf-8'),
            payload_b64.encode('utf-8'),
            hashlib.sha256
        ).digest()
        expected_signature_b64 = base64.urlsafe_b64encode(expected_signature).decode()

        if not hmac.compare_digest(signature_b64, expected_signature_b64):
            return False

        # Decode and check expiration
        payload_json = base64.urlsafe_b64decode(payload_b64).decode()
        payload = json.loads(payload_json)

        exp = payload.get('exp', 0)
        if exp < int(datetime.utcnow().timestamp()):
            return False

        return True
    except Exception:
        return False


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request."""
    # Check for X-Forwarded-For header (behind proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


def check_auth_cookie(request: Request) -> bool:
    """Check if the request has a valid session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    return verify_session_token(token, settings.secret_key)


def check_basic_auth(request: Request) -> bool:
    """
    Check if the request has valid HTTP Basic Auth credentials.

    For OSS password auth, we accept:
    - Username: empty or any value (ignored)
    - Password: must match RECONLY_AUTH_PASSWORD
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return False

    try:
        # Decode Base64 credentials
        encoded = auth_header[6:]  # Remove "Basic " prefix
        decoded = base64.b64decode(encoded).decode('utf-8')
        # Split username:password (username is ignored)
        if ':' not in decoded:
            return False
        _, password = decoded.split(':', 1)
        return timing_safe_compare(password, settings.reconly_auth_password or "")
    except Exception:
        return False


def is_public_route(path: str) -> bool:
    """Check if a route is public (doesn't require auth)."""
    # Normalize path (remove trailing slash for comparison)
    normalized = path.rstrip('/')

    public_prefixes = [
        "/health",
        "/api/health",
        f"{settings.api_v1_prefix}/health",
        f"{settings.api_v1_prefix}/auth",  # All auth routes are public
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    # Check exact matches and prefixes
    for prefix in public_prefixes:
        if normalized == prefix or normalized.startswith(prefix + "/") or normalized.startswith(prefix):
            return True

    return False


def requires_auth(func: Callable) -> Callable:
    """
    Decorator to require authentication on a route.

    This is used for explicit opt-in authentication on specific routes.
    For middleware-based auth on all routes, use the AuthMiddleware class.
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        # If no password is configured, auth is not required
        if not settings.auth_required:
            return await func(request, *args, **kwargs)

        # Check session cookie or Basic Auth
        if check_auth_cookie(request) or check_basic_auth(request):
            return await func(request, *args, **kwargs)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    return wrapper


async def verify_auth(request: Request) -> bool:
    """
    FastAPI dependency to verify authentication.

    Usage:
        @app.get("/protected")
        async def protected(authenticated: bool = Depends(verify_auth)):
            ...
    """
    # If no password is configured, always return True
    if not settings.auth_required:
        return True

    # Check public routes
    if is_public_route(request.url.path):
        return True

    # Check session cookie or Basic Auth
    if check_auth_cookie(request) or check_basic_auth(request):
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


def set_session_cookie(response: Response) -> None:
    """Set a session cookie on the response."""
    expires_at = datetime.utcnow() + timedelta(seconds=SESSION_COOKIE_MAX_AGE)
    token = create_session_token(settings.secret_key, expires_at)

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=SESSION_COOKIE_NAME)
