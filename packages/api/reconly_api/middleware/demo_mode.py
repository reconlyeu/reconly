"""Demo mode middleware that blocks write operations.

When RECONLY_DEMO_MODE is enabled, this middleware prevents any modifications
to the system by blocking POST, PUT, PATCH, and DELETE requests (except for
essential paths like authentication).

This allows hosting a public demo instance where users can explore the UI
but cannot make changes that would affect other users or persist data.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

from reconly_core.edition import is_demo_mode


class DemoModeMiddleware(BaseHTTPMiddleware):
    """Middleware that blocks write operations when RECONLY_DEMO_MODE is enabled.

    This middleware intercepts all incoming requests and checks if:
    1. Demo mode is enabled via RECONLY_DEMO_MODE environment variable
    2. The request method is a write operation (POST, PUT, PATCH, DELETE)
    3. The path is not in the allowed list (auth routes, health check)

    If all conditions are met, the request is blocked with a 403 response.

    Usage:
        from reconly_api.middleware import DemoModeMiddleware

        app.add_middleware(DemoModeMiddleware)
    """

    # HTTP methods that modify data and should be blocked in demo mode
    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Paths that should always be allowed, even for write methods.
    # These are essential for the app to function in demo mode:
    # - /health: Health checks for load balancers
    ALLOWED_PATHS = {
        "/health",
    }

    # Path prefixes that should be allowed (matches any path starting with these)
    # - /api/v1/auth/: All auth routes including OAuth callbacks
    ALLOWED_PATH_PREFIXES = (
        "/api/v1/auth/",
    )

    def __init__(self, app: Callable) -> None:
        """Initialize the demo mode middleware.

        Args:
            app: The ASGI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable):
        """Process the request and block write operations in demo mode.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The response from the next handler, or a 403 response if blocked
        """
        # Skip if not in demo mode - let everything through
        if not is_demo_mode():
            return await call_next(request)

        # Allow all read methods (GET, HEAD, OPTIONS)
        if request.method not in self.WRITE_METHODS:
            return await call_next(request)

        # Normalize path by removing trailing slash for comparison
        path = request.url.path.rstrip("/")

        # Allow certain exact paths (health check)
        if path in self.ALLOWED_PATHS:
            return await call_next(request)

        # Allow paths that start with allowed prefixes (auth routes including OAuth)
        if any(request.url.path.startswith(prefix) for prefix in self.ALLOWED_PATH_PREFIXES):
            return await call_next(request)

        # Block write operations with a helpful 403 message
        return JSONResponse(
            status_code=403,
            content={
                "detail": "Demo mode - modifications are disabled. Deploy your own instance to make changes."
            }
        )
