"""Connection schemas for API.

Connections provide reusable credential storage for email and other authenticated sources.
Credentials are encrypted at rest and NEVER exposed in API responses.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# Enums

class ConnectionType(str, Enum):
    """Connection type determines the credential structure."""
    EMAIL_IMAP = "email_imap"
    EMAIL_OAUTH = "email_oauth"
    HTTP_BASIC = "http_basic"
    API_KEY = "api_key"


class ConnectionProvider(str, Enum):
    """Provider for email connections (auto-fills host/port)."""
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    GENERIC = "generic"


# Config schemas (for validation)

class EmailIMAPConfig(BaseModel):
    """IMAP connection configuration."""
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(993, ge=1, le=65535)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)
    use_ssl: bool = True


class HTTPBasicConfig(BaseModel):
    """HTTP Basic authentication configuration."""
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)


class APIKeyConfig(BaseModel):
    """API key authentication configuration."""
    api_key: str = Field(..., min_length=1)
    endpoint: Optional[str] = Field(None, max_length=2048)


# Request schemas

# Maps connection types to their config validation schemas
CONFIG_VALIDATORS: dict[ConnectionType, type[BaseModel]] = {
    ConnectionType.EMAIL_IMAP: EmailIMAPConfig,
    ConnectionType.HTTP_BASIC: HTTPBasicConfig,
    ConnectionType.API_KEY: APIKeyConfig,
    # EMAIL_OAUTH handled via OAuth flow, not direct config
}


class ConnectionCreate(BaseModel):
    """Schema for creating a new connection.

    Config is a plaintext dict that gets encrypted before storage.
    """
    name: str = Field(..., min_length=1, max_length=255)
    type: ConnectionType
    provider: Optional[ConnectionProvider] = None
    config: dict[str, Any]

    @model_validator(mode='after')
    def validate_config_for_type(self):
        """Validate config matches the connection type."""
        validator = CONFIG_VALIDATORS.get(self.type)
        if validator:
            try:
                validator(**self.config)
            except Exception as e:
                raise ValueError(f"Invalid {self.type.value} config: {e}")
        return self

    @model_validator(mode='after')
    def default_provider_for_email(self):
        """Default to generic provider for email connections."""
        if self.type in (ConnectionType.EMAIL_IMAP, ConnectionType.EMAIL_OAUTH):
            if not self.provider:
                self.provider = ConnectionProvider.GENERIC
        return self


class ConnectionUpdate(BaseModel):
    """Schema for updating an existing connection (partial update)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    provider: Optional[ConnectionProvider] = None
    config: Optional[dict[str, Any]] = None


# Response schemas

class ConnectionResponse(BaseModel):
    """Connection response - credentials are NEVER included."""
    id: int
    name: str
    type: ConnectionType
    provider: Optional[ConnectionProvider] = None

    # Health tracking
    last_check_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None

    # Credential indicator (not the actual password)
    has_password: bool

    # Usage tracking
    source_count: int = 0

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ConnectionTestResult(BaseModel):
    """Result of testing a connection."""
    success: bool
    message: str
    response_time_ms: Optional[int] = None


class ConnectionListResponse(BaseModel):
    """Paginated list of connections."""
    total: int
    items: list[ConnectionResponse] = []
