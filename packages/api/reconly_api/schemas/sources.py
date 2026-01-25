"""Source schemas for API."""
import re
from typing import Optional, Dict, Any, List, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime


FilterMode = Literal["title_only", "content", "both"]
SourceType = Literal["rss", "youtube", "website", "blog", "imap", "agent"]
AuthStatus = Literal["active", "pending_oauth", "auth_failed"]
IMAPProvider = Literal["gmail", "outlook", "generic"]


class SourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: SourceType = Field(..., description="Source type")
    url: str = Field(..., max_length=2048)
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = True
    # Connection reference for sources using reusable credentials
    connection_id: Optional[int] = Field(None, description="ID of the Connection to use for credentials")
    # Content filtering
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    filter_mode: Optional[FilterMode] = "both"
    use_regex: Optional[bool] = False

    @model_validator(mode='after')
    def validate_regex_patterns(self):
        """Validate regex patterns if use_regex is enabled."""
        if not self.use_regex:
            return self

        for field_name in ['include_keywords', 'exclude_keywords']:
            patterns = getattr(self, field_name)
            if patterns:
                for pattern in patterns:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        raise ValueError(f"Invalid regex pattern '{pattern}' in {field_name}: {e}")
        return self


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[SourceType] = Field(None, description="Source type")
    url: Optional[str] = Field(None, max_length=2048)
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    # Connection reference for sources using reusable credentials
    connection_id: Optional[int] = Field(None, description="ID of the Connection to use for credentials")
    # Content filtering
    include_keywords: Optional[List[str]] = None
    exclude_keywords: Optional[List[str]] = None
    filter_mode: Optional[FilterMode] = None
    use_regex: Optional[bool] = None

    @model_validator(mode='after')
    def validate_regex_patterns(self):
        """Validate regex patterns if use_regex is enabled."""
        if not self.use_regex:
            return self

        for field_name in ['include_keywords', 'exclude_keywords']:
            patterns = getattr(self, field_name)
            if patterns:
                for pattern in patterns:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        raise ValueError(f"Invalid regex pattern '{pattern}' in {field_name}: {e}")
        return self


class SourceResponse(SourceBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    # Connection info - connection_id is inherited from SourceBase
    connection_name: Optional[str] = Field(
        None,
        description="Name of the associated Connection (for display in UI)"
    )
    # IMAP-specific fields
    auth_status: Optional[AuthStatus] = Field(
        None,
        description="Authentication status for IMAP sources: active, pending_oauth, auth_failed"
    )
    oauth_credential_id: Optional[int] = Field(
        None,
        description="ID of associated OAuth credential (for Gmail/Outlook sources)"
    )

    model_config = ConfigDict(from_attributes=True)


class IMAPSourceCreateRequest(BaseModel):
    """Request schema for creating an IMAP source.

    For OAuth providers (gmail, outlook), credentials are handled via OAuth flow.
    For generic IMAP, a connection_id referencing an email_imap Connection is required.
    """
    name: str = Field(..., min_length=1, max_length=255, description="Source name")
    provider: IMAPProvider = Field(..., description="IMAP provider type")
    # Connection reference for generic IMAP - credentials come from Connection
    connection_id: Optional[int] = Field(
        None,
        description="ID of email_imap Connection to use for credentials (required for generic IMAP)"
    )
    # Content filtering (optional)
    include_keywords: Optional[List[str]] = Field(None, description="Keywords to include")
    exclude_keywords: Optional[List[str]] = Field(None, description="Keywords to exclude")
    filter_mode: Optional[FilterMode] = Field("both", description="Filter mode")
    use_regex: Optional[bool] = Field(False, description="Interpret keywords as regex")
    # Email filtering
    folders: Optional[List[str]] = Field(None, description="IMAP folders to fetch (default: INBOX)")
    from_filter: Optional[str] = Field(None, description="Filter emails by sender pattern")
    subject_filter: Optional[str] = Field(None, description="Filter emails by subject pattern")

    @model_validator(mode='after')
    def validate_generic_imap_fields(self):
        """Validate that generic IMAP has a connection_id."""
        if self.provider == "generic":
            if not self.connection_id:
                raise ValueError("connection_id is required for generic IMAP provider")
        return self


class IMAPSourceCreateResponse(BaseModel):
    """Response schema for IMAP source creation.

    For OAuth providers, includes oauth_url for user to complete OAuth flow.
    For generic IMAP, returns created source directly.
    """
    source: SourceResponse = Field(..., description="Created source")
    oauth_url: Optional[str] = Field(
        None,
        description="OAuth authorization URL (for gmail/outlook providers)"
    )
    message: str = Field(..., description="Status message")


# Health status types
HealthStatus = Literal["healthy", "degraded", "unhealthy"]


class SourceHealthResponse(BaseModel):
    """Health status for a single source.

    Provides detailed health information including circuit breaker state
    and failure tracking for resilience monitoring.
    """
    source_id: int = Field(..., description="Source ID")
    source_name: str = Field(..., description="Source name")
    health_status: HealthStatus = Field(..., description="Current health status")
    consecutive_failures: int = Field(..., description="Number of consecutive failures")
    last_failure_at: Optional[datetime] = Field(None, description="When the most recent failure occurred")
    last_success_at: Optional[datetime] = Field(None, description="When the most recent success occurred")
    circuit_open_until: Optional[datetime] = Field(None, description="When circuit breaker will attempt recovery")
    is_circuit_open: bool = Field(..., description="Whether the circuit breaker is currently open")

    model_config = ConfigDict(from_attributes=True)


class SourcesHealthSummary(BaseModel):
    """Aggregate health status across all sources.

    Provides a summary of source health for monitoring dashboards
    and alerting systems.
    """
    healthy: int = Field(..., description="Number of healthy sources")
    degraded: int = Field(..., description="Number of degraded sources")
    unhealthy: int = Field(..., description="Number of unhealthy sources")
    total: int = Field(..., description="Total number of sources")
    sources: Optional[List[SourceHealthResponse]] = Field(
        None,
        description="Detailed health info per source (only if include_details=true)"
    )


class ValidationResponse(BaseModel):
    """Response from source URL validation.

    Provides validation results including any test fetch metrics
    when test_fetch is enabled.
    """
    valid: bool = Field(..., description="Whether the source URL is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    test_item_count: Optional[int] = Field(
        None,
        description="Number of items found during test fetch (if test_fetch=true)"
    )
    response_time_ms: Optional[float] = Field(
        None,
        description="Response time in milliseconds (if test_fetch=true)"
    )
    url_type: Optional[str] = Field(
        None,
        description="Detected URL type (e.g., 'rss', 'youtube_channel', 'youtube_video')"
    )
