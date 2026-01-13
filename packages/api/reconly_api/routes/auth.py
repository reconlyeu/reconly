"""Authentication routes for OSS password protection.

Provides endpoints for:
- POST /api/auth/login - Authenticate with password, get session cookie
- POST /api/auth/logout - Clear session cookie
- GET /api/config - Check if auth is required (public endpoint)
"""
from fastapi import APIRouter, HTTPException, Request, Response, status

from reconly_api.config import settings
from reconly_api.auth.password import (
    ConfigResponse,
    LoginRequest,
    LoginResponse,
    clear_session_cookie,
    get_client_ip,
    set_session_cookie,
    timing_safe_compare,
    _is_rate_limited,
    _record_failed_attempt,
    _clear_failed_attempts,
)


router = APIRouter()


@router.post("/login/", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest, response: Response):
    """
    Authenticate with password and receive a session cookie.

    Rate limited to 5 failed attempts per IP per minute.
    """
    client_ip = get_client_ip(request)

    # Check rate limiting
    if _is_rate_limited(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
        )

    # If no password is configured, auth is not enabled
    if not settings.auth_required:
        return LoginResponse(
            success=True,
            message="Authentication not required",
        )

    # Verify password using timing-safe comparison
    if not timing_safe_compare(body.password, settings.reconly_auth_password or ""):
        _record_failed_attempt(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Success - clear failed attempts and set session cookie
    _clear_failed_attempts(client_ip)
    set_session_cookie(response)

    return LoginResponse(
        success=True,
        message="Login successful",
    )


@router.post("/logout/", response_model=LoginResponse)
async def logout(response: Response):
    """
    Clear the session cookie.

    Always succeeds, even if not logged in.
    """
    clear_session_cookie(response)
    return LoginResponse(
        success=True,
        message="Logged out successfully",
    )


@router.get("/config/", response_model=ConfigResponse)
async def get_config():
    """
    Get authentication configuration.

    This is a public endpoint that returns whether authentication is required.
    Used by the UI to determine if it should show a login page.
    """
    return ConfigResponse(
        auth_required=settings.auth_required,
        edition=settings.reconly_edition,
    )
