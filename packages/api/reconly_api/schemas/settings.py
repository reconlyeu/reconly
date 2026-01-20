"""Settings schemas for API."""
from typing import Any, Literal
from pydantic import BaseModel, EmailStr, Field


# ─────────────────────────────────────────────────────────────────────────────
# Settings schemas
# ─────────────────────────────────────────────────────────────────────────────

class SettingValue(BaseModel):
    """A single setting with source indicator."""
    value: Any = Field(..., description="The effective value")
    source: Literal["database", "environment", "default"] = Field(
        ..., description="Where the value comes from"
    )
    editable: bool = Field(..., description="Whether user can modify this setting")


class SettingsResponse(BaseModel):
    """Settings organized by category with source indicators."""
    provider: dict[str, SettingValue] = Field(
        default_factory=dict, description="LLM provider settings"
    )
    email: dict[str, SettingValue] = Field(
        default_factory=dict, description="Email/SMTP settings"
    )
    export: dict[str, SettingValue] = Field(
        default_factory=dict, description="Export settings"
    )
    fetch: dict[str, SettingValue] = Field(
        default_factory=dict, description="Fetcher settings (RSS, YouTube, etc.)"
    )
    embedding: dict[str, SettingValue] = Field(
        default_factory=dict, description="RAG embedding settings"
    )
    rag: dict[str, SettingValue] = Field(
        default_factory=dict, description="RAG system settings"
    )
    agent: dict[str, SettingValue] = Field(
        default_factory=dict, description="Agent research settings"
    )
    resilience: dict[str, SettingValue] = Field(
        default_factory=dict, description="Circuit breaker, retry, and validation settings"
    )


class SettingUpdateRequest(BaseModel):
    """Request to update a single setting."""
    key: str = Field(..., description="Setting key (e.g., 'llm.default_provider')")
    value: Any = Field(..., description="New value")


class SettingsUpdateRequest(BaseModel):
    """Request to update multiple settings."""
    settings: list[SettingUpdateRequest] = Field(
        ..., description="List of settings to update"
    )


class SettingsResetRequest(BaseModel):
    """Request to reset settings to defaults."""
    keys: list[str] = Field(..., description="Setting keys to reset")


class SettingsResetResponse(BaseModel):
    """Response from reset operation."""
    reset: list[str] = Field(..., description="Keys that were reset")
    not_found: list[str] = Field(default_factory=list, description="Keys that had no DB override")


class TestEmailRequest(BaseModel):
    """Test email request."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field("Reconly Test Email", description="Email subject")
    body: str = Field("This is a test email from Reconly.", description="Email body")


class TestEmailResponse(BaseModel):
    """Test email response."""
    success: bool
    message: str
