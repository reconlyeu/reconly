"""API schemas package.

Schemas are typically imported directly from their modules:
    from reconly_api.schemas.connections import ConnectionCreate, ConnectionResponse
    from reconly_api.schemas.feeds import FeedCreate, FeedResponse

This __init__.py exports key schemas for convenience.
"""

# Connection schemas
from reconly_api.schemas.connections import (
    ConnectionType,
    ConnectionProvider,
    EmailIMAPConfig,
    HTTPBasicConfig,
    APIKeyConfig,
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionTestResult,
    ConnectionListResponse,
)

__all__ = [
    # Connection schemas
    "ConnectionType",
    "ConnectionProvider",
    "EmailIMAPConfig",
    "HTTPBasicConfig",
    "APIKeyConfig",
    "ConnectionCreate",
    "ConnectionUpdate",
    "ConnectionResponse",
    "ConnectionTestResult",
    "ConnectionListResponse",
]
