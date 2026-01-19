"""Component metadata schemas for API responses.

This module defines Pydantic models for returning component metadata in API responses.
These schemas map to the dataclasses defined in reconly_core for providers, fetchers,
and exporters.

Security Note: Sensitive fields like env_var names are NOT exposed to the frontend.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ComponentMetadataResponse(BaseModel):
    """Base metadata response for all component types.

    This is the common structure shared by providers, fetchers, and exporters.
    Component-specific responses extend this with additional fields.
    """

    name: str = Field(..., description="Internal identifier (e.g., 'ollama', 'rss', 'json')")
    display_name: str = Field(..., description="Human-readable name for UI display")
    description: str = Field(..., description="Short description of the component")
    icon: Optional[str] = Field(
        default=None, description="Icon identifier for UI (iconify format, e.g., 'mdi:rss')"
    )

    model_config = ConfigDict(from_attributes=True)


class ProviderMetadataResponse(ComponentMetadataResponse):
    """Provider metadata in API response.

    Extends ComponentMetadataResponse with provider-specific fields.

    Security Note: Environment variable names (api_key_env_var, base_url_env_var, etc.)
    are intentionally NOT exposed to prevent information disclosure.
    """

    is_local: bool = Field(..., description="Whether provider runs locally (vs. cloud API)")
    requires_api_key: bool = Field(..., description="Whether provider requires an API key")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "ollama",
                "display_name": "Ollama",
                "description": "Local LLM via Ollama server",
                "icon": "mdi:robot",
                "is_local": True,
                "requires_api_key": False,
            }
        },
    )


class FetcherMetadataResponse(ComponentMetadataResponse):
    """Fetcher metadata in API response.

    Extends ComponentMetadataResponse with fetcher-specific fields for
    URL scheme support, OAuth capabilities, and feature flags.
    """

    url_schemes: list[str] = Field(
        default_factory=list,
        description="URL schemes this fetcher handles (e.g., ['http', 'https'])",
    )
    supports_oauth: bool = Field(default=False, description="Whether fetcher supports OAuth")
    oauth_providers: list[str] = Field(
        default_factory=list,
        description="OAuth providers supported (e.g., ['gmail', 'outlook'])",
    )
    supports_incremental: bool = Field(
        default=False, description="Whether fetcher supports incremental/delta fetching"
    )
    supports_validation: bool = Field(
        default=True, description="Whether fetcher supports URL/config validation"
    )
    supports_test_fetch: bool = Field(
        default=True, description="Whether fetcher supports test fetching during validation"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "rss",
                "display_name": "RSS Feed",
                "description": "Fetch content from RSS/Atom feeds",
                "icon": "mdi:rss",
                "url_schemes": ["http", "https"],
                "supports_oauth": False,
                "oauth_providers": [],
                "supports_incremental": True,
                "supports_validation": True,
                "supports_test_fetch": True,
            }
        },
    )


class ExporterMetadataResponse(ComponentMetadataResponse):
    """Exporter metadata in API response.

    Extends ComponentMetadataResponse with exporter-specific fields for
    file format information and UI styling.

    Security Note: path_setting_key is intentionally NOT exposed as it's
    an internal configuration detail.
    """

    file_extension: str = Field(..., description="File extension for exported files (e.g., '.json')")
    mime_type: str = Field(..., description="MIME type for HTTP responses")
    ui_color: Optional[str] = Field(
        default=None, description="Hex color code for UI theming (e.g., '#7C3AED')"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "obsidian",
                "display_name": "Obsidian",
                "description": "Export digests to Obsidian vault with frontmatter",
                "icon": "simple-icons:obsidian",
                "file_extension": ".md",
                "mime_type": "text/markdown",
                "ui_color": "#7C3AED",
            }
        },
    )
