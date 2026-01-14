"""Security headers middleware for FastAPI.

This middleware adds security headers to all responses to protect against
common web vulnerabilities like XSS, clickjacking, and MIME-type sniffing.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses.

    Headers added:
    - Content-Security-Policy: Controls which resources can be loaded
    - X-Frame-Options: Prevents clickjacking by disabling framing
    - X-Content-Type-Options: Prevents MIME-type sniffing
    - Referrer-Policy: Controls referrer information sent with requests
    - X-XSS-Protection: Legacy XSS protection for older browsers

    Usage:
        from reconly_api.middleware import SecurityHeadersMiddleware
        from reconly_api.config import settings

        app.add_middleware(SecurityHeadersMiddleware, csp_policy=settings.csp_policy)
    """

    def __init__(self, app: Callable, csp_policy: str | None = None) -> None:
        """Initialize the security headers middleware.

        Args:
            app: The ASGI application
            csp_policy: Custom Content-Security-Policy header value.
                       If None, uses a sensible default.
        """
        super().__init__(app)
        self.csp_policy = csp_policy or (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "connect-src 'self'"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add security headers to the response."""
        response = await call_next(request)

        response.headers["Content-Security-Policy"] = self.csp_policy
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response
