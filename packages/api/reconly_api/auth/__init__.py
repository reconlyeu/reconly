"""Authentication module.

OSS Edition:
- Optional password protection via SKIMBERRY_AUTH_PASSWORD
- Session-based auth with signed cookies
- HTTP Basic Auth support for CLI/scripts

Enterprise Edition:
- Full user management (implemented in reconly-enterprise)
- JWT tokens with user context
"""
from reconly_api.auth.jwt import get_current_active_user
from reconly_api.auth.password import (
    verify_auth,
    requires_auth,
    LoginRequest,
    LoginResponse,
    ConfigResponse,
)

__all__ = [
    "get_current_active_user",
    "verify_auth",
    "requires_auth",
    "LoginRequest",
    "LoginResponse",
    "ConfigResponse",
]
