"""Settings schemas for API."""
from typing import Optional, Any, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ─────────────────────────────────────────────────────────────────────────────
# New settings infrastructure schemas (Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

class SettingValue(BaseModel):
    """A single setting with source indicator."""
    value: Any = Field(..., description="The effective value")
    source: Literal["database", "environment", "default"] = Field(
        ..., description="Where the value comes from"
    )
    editable: bool = Field(..., description="Whether user can modify this setting")


class SettingsResponseV2(BaseModel):
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
    embedding: dict[str, SettingValue] = Field(
        default_factory=dict, description="RAG embedding settings"
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


# ─────────────────────────────────────────────────────────────────────────────
# Legacy settings schemas (kept for backwards compatibility)
# ─────────────────────────────────────────────────────────────────────────────

class SMTPSettings(BaseModel):
    """SMTP email configuration."""
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(..., ge=1, le=65535, description="SMTP server port")
    smtp_user: Optional[str] = Field(None, description="SMTP username")
    smtp_password: Optional[str] = Field(None, description="SMTP password (will be masked in responses)")
    smtp_from_email: EmailStr = Field(..., description="From email address")
    smtp_from_name: str = Field("Reconly", description="From name")


class ExportSettings(BaseModel):
    """Export configuration."""
    obsidian_vault_path: Optional[str] = Field(None, description="Path to Obsidian vault")
    default_export_format: str = Field("json", description="Default export format (json/csv/obsidian)")


class SettingsResponse(BaseModel):
    """Complete settings response."""
    smtp: SMTPSettings
    exports: ExportSettings
    demo_mode: bool = Field(False, description="Whether the application is running in demo mode")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "smtp": {
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "smtp_user": "user@example.com",
                "smtp_password": "***",
                "smtp_from_email": "reconly@example.com",
                "smtp_from_name": "Reconly"
            },
            "exports": {
                "obsidian_vault_path": "/path/to/vault",
                "default_export_format": "json"
            },
            "demo_mode": False
        }
    })


class SettingsUpdate(BaseModel):
    """Settings update request."""
    smtp: Optional[SMTPSettings] = None
    exports: Optional[ExportSettings] = None


class TestEmailRequest(BaseModel):
    """Test email request."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field("Reconly Test Email", description="Email subject")
    body: str = Field("This is a test email from Reconly.", description="Email body")


class TestEmailResponse(BaseModel):
    """Test email response."""
    success: bool
    message: str
