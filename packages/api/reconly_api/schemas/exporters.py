"""Exporter-related schemas."""
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from reconly_api.schemas.common import ConfigFieldResponse


class ExporterConfigSchemaResponse(BaseModel):
    """Schema for exporter configuration schema."""
    fields: List[ConfigFieldResponse] = Field(default_factory=list)
    supports_direct_export: bool = Field(default=False)

    model_config = ConfigDict(from_attributes=True)


class ExporterResponse(BaseModel):
    """Schema for single exporter in list response."""
    name: str = Field(..., description="Format name (e.g., 'json', 'obsidian')")
    description: str = Field(..., description="Human-readable description")
    content_type: str = Field(..., description="MIME type")
    file_extension: str = Field(..., description="File extension without dot")
    supports_direct_export: bool = Field(default=False, description="Can write to filesystem")
    config_schema: ExporterConfigSchemaResponse = Field(
        ..., description="Configuration options"
    )
    # Activation state fields
    enabled: bool = Field(default=True, description="Whether exporter is enabled")
    is_configured: bool = Field(default=True, description="Whether all required config fields have values")
    can_enable: bool = Field(default=True, description="Whether exporter can be enabled")
    # Extension flag
    is_extension: bool = Field(default=False, description="Whether this is an external extension")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "obsidian",
            "description": "Markdown with Obsidian YAML frontmatter",
            "content_type": "text/markdown",
            "file_extension": "md",
            "supports_direct_export": True,
            "config_schema": {
                "fields": [
                    {
                        "key": "vault_path",
                        "type": "path",
                        "label": "Vault Path",
                        "description": "Path to your Obsidian vault",
                        "default": None,
                        "required": True,
                        "placeholder": "/path/to/vault"
                    }
                ],
                "supports_direct_export": True
            },
            "enabled": False,
            "is_configured": False,
            "can_enable": False
        }
    })


class ExporterListResponse(BaseModel):
    """Schema for list of exporters."""
    exporters: List[ExporterResponse] = Field(..., description="Available exporters")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "exporters": [
                {
                    "name": "json",
                    "description": "JSON format",
                    "content_type": "application/json",
                    "file_extension": "json",
                    "supports_direct_export": False,
                    "config_schema": {"fields": [], "supports_direct_export": False}
                }
            ]
        }
    })


class ExportToPathRequest(BaseModel):
    """Schema for export-to-path request."""
    format: str = Field(
        default="obsidian",
        description="Export format (must support direct export)"
    )
    path: Optional[str] = Field(
        default=None,
        description="Custom target path (uses configured path if omitted)"
    )
    digest_ids: Optional[list[int]] = Field(
        default=None,
        description="Specific digest IDs to export (overrides filters)"
    )
    feed_id: Optional[int] = Field(default=None, description="Filter by feed ID")
    source_id: Optional[int] = Field(default=None, description="Filter by source ID")
    tag: Optional[str] = Field(default=None, description="Filter by tag")
    search: Optional[str] = Field(default=None, description="Search query")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "format": "obsidian",
            "path": None,
            "digest_ids": [1, 2, 3],
            "feed_id": 1,
            "tag": "tech"
        }
    })


class ExportByIdsRequest(BaseModel):
    """Schema for exporting specific digests by ID."""
    ids: list[int] = Field(..., description="List of digest IDs to export")
    format: str = Field(default="json", description="Export format (json, csv, obsidian)")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "ids": [1, 2, 3],
            "format": "json"
        }
    })


class ExportToPathResponse(BaseModel):
    """Schema for export-to-path response."""
    success: bool = Field(..., description="Whether all files written successfully")
    files_written: int = Field(..., description="Number of files written")
    files_skipped: int = Field(default=0, description="Number of files skipped (already exist)")
    target_path: str = Field(..., description="Directory where files were written")
    filenames: List[str] = Field(default_factory=list, description="Written filenames")
    errors: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Errors for failed writes"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "files_written": 5,
            "files_skipped": 2,
            "target_path": "/path/to/vault",
            "filenames": ["2026-01-08-article.md", "2026-01-08-news.md"],
            "errors": []
        }
    })


class ExporterToggleRequest(BaseModel):
    """Schema for toggling exporter enabled state."""
    enabled: bool = Field(..., description="Whether to enable or disable the exporter")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "enabled": True
        }
    })
