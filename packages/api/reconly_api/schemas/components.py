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
    URL scheme support, OAuth capabilities, connection requirements, and feature flags.
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
    show_in_settings: bool = Field(
        default=True, description="Whether fetcher should appear in settings UI"
    )
    requires_connection: bool = Field(
        default=False, description="Whether fetcher requires a Connection for credentials"
    )
    connection_types: list[str] = Field(
        default_factory=list,
        description="Supported connection types (e.g., ['email_imap'])",
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
                "show_in_settings": True,
                "requires_connection": False,
                "connection_types": [],
            }
        },
    )


class EmbeddingProviderMetadataResponse(ComponentMetadataResponse):
    """Embedding provider metadata in API response.

    Extends ComponentMetadataResponse with embedding provider-specific fields
    for API key requirements, base URL support, and model configuration.
    """

    requires_api_key: bool = Field(
        default=True, description="Whether provider requires an API key"
    )
    supports_base_url: bool = Field(
        default=False, description="Whether provider supports custom base URL"
    )
    model_param_name: str = Field(
        default="model", description="Parameter name for model selection"
    )
    is_local: bool = Field(
        default=False, description="Whether provider runs locally"
    )
    default_model: Optional[str] = Field(
        default=None, description="Default model for the provider"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "ollama",
                "display_name": "Ollama",
                "description": "Local embedding via Ollama server",
                "icon": "simple-icons:ollama",
                "requires_api_key": False,
                "supports_base_url": True,
                "model_param_name": "model",
                "is_local": True,
                "default_model": "bge-m3",
            }
        },
    )


class ExporterMetadataResponse(ComponentMetadataResponse):
    """Exporter metadata in API response.

    Extends ComponentMetadataResponse with exporter-specific fields for
    file format information, connection requirements, and UI styling.
    """

    file_extension: str = Field(..., description="File extension for exported files (e.g., '.json')")
    mime_type: str = Field(..., description="MIME type for HTTP responses")
    path_setting_key: str = Field(
        default="export_path",
        description="Configuration key for export path setting (e.g., 'export_path', 'vault_path')",
    )
    ui_color: Optional[str] = Field(
        default=None, description="Hex color code for UI theming (e.g., '#7C3AED')"
    )
    requires_connection: bool = Field(
        default=False, description="Whether exporter requires a Connection for credentials"
    )
    connection_types: list[str] = Field(
        default_factory=list,
        description="Supported connection types (e.g., ['http_basic', 'api_key'])",
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
                "path_setting_key": "vault_path",
                "ui_color": "#7C3AED",
                "requires_connection": False,
                "connection_types": [],
            }
        },
    )
