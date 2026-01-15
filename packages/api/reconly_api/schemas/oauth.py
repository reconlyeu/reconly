"""OAuth2 schemas for API requests and responses."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class OAuthProviderInfo(BaseModel):
    """Information about a supported OAuth provider."""
    provider: Literal["gmail", "outlook"] = Field(..., description="OAuth provider name")
    display_name: str = Field(..., description="Human-readable provider name")
    scopes: List[str] = Field(..., description="OAuth scopes that will be requested")
    configured: bool = Field(..., description="Whether provider credentials are configured")


class OAuthProvidersResponse(BaseModel):
    """List of available OAuth providers."""
    providers: List[OAuthProviderInfo] = Field(..., description="Available OAuth providers")


class OAuthAuthorizeRequest(BaseModel):
    """Request to initiate OAuth authorization flow."""
    source_id: int = Field(..., description="Source ID to associate with this OAuth connection")


class OAuthAuthorizeResponse(BaseModel):
    """Response containing OAuth authorization URL."""
    authorization_url: str = Field(..., description="URL to redirect user to for OAuth consent")
    provider: Literal["gmail", "outlook"] = Field(..., description="OAuth provider")


class OAuthCallbackResponse(BaseModel):
    """Response after successful OAuth callback."""
    success: bool = Field(..., description="Whether OAuth flow completed successfully")
    source_id: int = Field(..., description="Source ID the OAuth is connected to")
    provider: Literal["gmail", "outlook"] = Field(..., description="OAuth provider")
    message: str = Field(..., description="Human-readable status message")


class OAuthCredentialResponse(BaseModel):
    """OAuth credential information (without sensitive token data)."""
    id: int = Field(..., description="Credential ID")
    source_id: int = Field(..., description="Associated source ID")
    provider: Literal["gmail", "outlook"] = Field(..., description="OAuth provider")
    expires_at: Optional[datetime] = Field(None, description="When the access token expires")
    scopes: Optional[List[str]] = Field(None, description="Granted OAuth scopes")
    has_refresh_token: bool = Field(..., description="Whether a refresh token is stored")
    created_at: datetime = Field(..., description="When the credential was created")
    updated_at: Optional[datetime] = Field(None, description="When the credential was last updated")

    model_config = ConfigDict(from_attributes=True)


class OAuthRevokeResponse(BaseModel):
    """Response after OAuth token revocation."""
    success: bool = Field(..., description="Whether revocation was successful")
    source_id: int = Field(..., description="Source ID whose OAuth was revoked")
    provider: Literal["gmail", "outlook"] = Field(..., description="OAuth provider")
    message: str = Field(..., description="Human-readable status message")


class OAuthStatusResponse(BaseModel):
    """OAuth connection status for a source."""
    connected: bool = Field(..., description="Whether OAuth is connected")
    provider: Optional[Literal["gmail", "outlook"]] = Field(
        None, description="OAuth provider if connected"
    )
    expires_at: Optional[datetime] = Field(
        None, description="When the access token expires"
    )
    needs_refresh: bool = Field(
        False, description="Whether the token needs refresh"
    )
    has_refresh_token: bool = Field(
        False, description="Whether a refresh token is available"
    )


class OAuthErrorResponse(BaseModel):
    """Error response for OAuth operations."""
    error: str = Field(..., description="Error code")
    error_description: str = Field(..., description="Human-readable error description")
    provider: Optional[Literal["gmail", "outlook"]] = Field(
        None, description="OAuth provider if known"
    )
