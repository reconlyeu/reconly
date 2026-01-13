"""Extension-related schemas.

Extensions API returns metadata and lifecycle status only.
Configuration details are available via component-specific APIs:
- /api/v1/exporters/{name}/ for exporter configuration
- /api/v1/fetchers/{name}/ for fetcher configuration
- /api/v1/providers/{name}/ for provider configuration
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExtensionMetadataResponse(BaseModel):
    """Schema for extension metadata."""
    name: str = Field(..., description="Human-readable extension name")
    version: str = Field(..., description="Extension version")
    author: str = Field(..., description="Author name")
    min_reconly: str = Field(..., description="Minimum Reconly version required")
    description: str = Field(..., description="Extension description")
    homepage: Optional[str] = Field(default=None, description="Extension homepage URL")
    type: str = Field(..., description="Extension type (exporter, fetcher, provider)")
    registry_name: str = Field(..., description="Name in registry (e.g., 'notion')")

    model_config = ConfigDict(from_attributes=True)


class ExtensionResponse(BaseModel):
    """Schema for single extension in list response.

    Note: config_schema has been removed. Configuration is now handled
    by component-specific APIs. Use the config_api field to find the
    appropriate endpoint for configuration.
    """
    name: str = Field(..., description="Registry name (e.g., 'notion')")
    type: str = Field(..., description="Extension type (exporter, fetcher, provider)")
    metadata: ExtensionMetadataResponse = Field(..., description="Extension metadata")
    is_extension: bool = Field(default=True, description="Whether this is an external extension")
    enabled: bool = Field(default=False, description="Whether extension is enabled")
    is_configured: bool = Field(default=True, description="Whether all required config fields have values")
    can_enable: bool = Field(default=True, description="Whether extension can be enabled")
    load_error: Optional[str] = Field(default=None, description="Error message if extension failed to load")
    config_api: str = Field(
        ...,
        description="API path for configuration (e.g., '/api/v1/exporters/notion/')"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "notion",
            "type": "exporter",
            "metadata": {
                "name": "Notion Exporter",
                "version": "1.0.0",
                "author": "Community",
                "min_reconly": "0.5.0",
                "description": "Export digests to Notion databases",
                "homepage": "https://github.com/reconly/reconly-extensions",
                "type": "exporter",
                "registry_name": "notion"
            },
            "is_extension": True,
            "enabled": False,
            "is_configured": False,
            "can_enable": False,
            "load_error": None,
            "config_api": "/api/v1/exporters/notion/"
        }
    })


class ExtensionListResponse(BaseModel):
    """Schema for list of extensions."""
    total: int = Field(..., description="Total number of extensions")
    items: List[ExtensionResponse] = Field(..., description="Extension list")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 1,
            "items": [
                {
                    "name": "notion",
                    "type": "exporter",
                    "metadata": {
                        "name": "Notion Exporter",
                        "version": "1.0.0",
                        "author": "Community",
                        "min_reconly": "0.5.0",
                        "description": "Export digests to Notion",
                        "homepage": None,
                        "type": "exporter",
                        "registry_name": "notion"
                    },
                    "is_extension": True,
                    "enabled": True,
                    "is_configured": True,
                    "can_enable": True,
                    "config_api": "/api/v1/exporters/notion/"
                }
            ]
        }
    })


class ExtensionToggleRequest(BaseModel):
    """Schema for toggling extension enabled state."""
    enabled: bool = Field(..., description="Whether to enable or disable the extension")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "enabled": True
        }
    })


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: CATALOG & INSTALLATION
# ═══════════════════════════════════════════════════════════════════════════════


class CatalogEntryResponse(BaseModel):
    """Schema for a single extension in the catalog."""
    package: str = Field(..., description="PyPI package name (e.g., 'reconly-ext-notion')")
    name: str = Field(..., description="Human-readable name")
    type: str = Field(..., description="Extension type (exporter, fetcher, provider)")
    description: str = Field(..., description="Brief description")
    author: str = Field(..., description="Author name or organization")
    version: str = Field(default="0.0.0", description="Latest available version")
    verified: bool = Field(default=False, description="Whether extension is verified/curated")
    homepage: Optional[str] = Field(default=None, description="Extension homepage URL")
    pypi_url: Optional[str] = Field(default=None, description="PyPI package URL")
    installed: bool = Field(default=False, description="Whether currently installed")
    installed_version: Optional[str] = Field(default=None, description="Installed version if installed")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "package": "reconly-ext-notion",
            "name": "Notion Exporter",
            "type": "exporter",
            "description": "Export digests to Notion databases",
            "author": "Community",
            "version": "1.0.0",
            "verified": True,
            "homepage": "https://github.com/reconly/reconly-extensions",
            "pypi_url": "https://pypi.org/project/reconly-ext-notion/",
            "installed": False,
            "installed_version": None
        }
    })


class CatalogResponse(BaseModel):
    """Schema for the extension catalog."""
    version: str = Field(..., description="Catalog schema version")
    extensions: List[CatalogEntryResponse] = Field(..., description="Available extensions")
    last_updated: Optional[str] = Field(default=None, description="When catalog was last updated")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "version": "1.0",
            "extensions": [
                {
                    "package": "reconly-ext-notion",
                    "name": "Notion Exporter",
                    "type": "exporter",
                    "description": "Export digests to Notion databases",
                    "author": "Community",
                    "version": "1.0.0",
                    "verified": True,
                    "installed": False
                }
            ],
            "last_updated": "2026-01-10T00:00:00Z"
        }
    })


class ExtensionInstallRequest(BaseModel):
    """Schema for installing an extension."""
    package: str = Field(
        ...,
        description="Package name to install (must start with 'reconly-ext-')",
        min_length=14  # len("reconly-ext-") = 14
    )
    upgrade: bool = Field(default=False, description="Upgrade if already installed")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "package": "reconly-ext-notion",
            "upgrade": False
        }
    })


class ExtensionInstallResponse(BaseModel):
    """Schema for install/uninstall result."""
    success: bool = Field(..., description="Whether operation succeeded")
    package: str = Field(..., description="Package that was operated on")
    version: Optional[str] = Field(default=None, description="Installed version (for install)")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    requires_restart: bool = Field(default=True, description="Whether restart is needed")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "package": "reconly-ext-notion",
            "version": "1.0.0",
            "error": None,
            "requires_restart": True
        }
    })
