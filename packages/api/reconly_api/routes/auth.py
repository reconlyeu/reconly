"""Authentication routes for OSS password protection.

Provides endpoints for:
- POST /api/auth/login - Authenticate with password, get session cookie
- POST /api/auth/logout - Clear session cookie
- GET /api/config - Check if auth is required (public endpoint)

All authentication events are logged via the audit logging system for
security monitoring and compliance.
"""
from fastapi import APIRouter, HTTPException, Request, Response, status

from reconly_api.audit import AuditEventType, audit_log
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


@router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest, response: Response):
    """
    Authenticate with password and receive a session cookie.

    Rate limited to 5 failed attempts per IP per minute.
    All login attempts (success and failure) are logged for security auditing.
    """
    client_ip = get_client_ip(request)

    # Check rate limiting
    if _is_rate_limited(client_ip):
        # Log rate limit event
        audit_log(
            AuditEventType.RATE_LIMITED,
            ip=client_ip,
            details={"endpoint": "/auth/login", "reason": "too_many_failed_attempts"},
        )
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

        # Log failed authentication attempt (never log the actual password)
        audit_log(
            AuditEventType.AUTH_FAILURE,
            ip=client_ip,
            details={"reason": "invalid_password"},
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Success - clear failed attempts and set session cookie
    _clear_failed_attempts(client_ip)
    set_session_cookie(response, request)

    # Log successful authentication
    audit_log(
        AuditEventType.AUTH_SUCCESS,
        ip=client_ip,
    )

    return LoginResponse(
        success=True,
        message="Login successful",
    )


@router.post("/logout", response_model=LoginResponse)
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


@router.get("/config", response_model=ConfigResponse)
async def get_config(request: Request):
    """
    Get authentication configuration.

    This is a public endpoint that returns whether authentication is required
    and whether the current user is authenticated (has valid session).
    Used by the UI to determine if it should show a login page.
    """
    from reconly_api.auth.password import check_auth_cookie, check_basic_auth

    # Check if user is authenticated via cookie or basic auth
    is_authenticated = False
    if not settings.auth_required:
        # No auth required means everyone is "authenticated"
        is_authenticated = True
    else:
        is_authenticated = check_auth_cookie(request) or check_basic_auth(request)

    return ConfigResponse(
        auth_required=settings.auth_required,
        authenticated=is_authenticated,
        edition=settings.reconly_edition,
    )
