"""Exporter-specific metadata for digest exporters.

This module defines the ExporterMetadata dataclass that extends ComponentMetadata
with exporter-specific fields for file extension, MIME type, and export path configuration.

Example:
    >>> from reconly_core.exporters.metadata import ExporterMetadata
    >>> metadata = ExporterMetadata(
    ...     name="json",
    ...     display_name="JSON",
    ...     description="Export digests as JSON files",
    ...     icon="mdi:code-json",
    ...     file_extension=".json",
    ...     mime_type="application/json",
    ... )
    >>> metadata.to_dict()
    {'name': 'json', 'display_name': 'JSON', ...}
"""
from dataclasses import dataclass, field
from typing import Any

from reconly_core.metadata import ComponentMetadata


@dataclass
class ExporterMetadata(ComponentMetadata):
    """Metadata for digest exporters.

    Extends ComponentMetadata with exporter-specific configuration including
    file extension, MIME type, export path configuration, and connection requirements.

    Attributes:
        name: Internal identifier (e.g., 'json', 'csv', 'obsidian').
        display_name: Human-readable name (e.g., 'JSON', 'CSV', 'Obsidian').
        description: Short description of the exporter.
        icon: Icon identifier for UI (e.g., 'mdi:code-json', 'mdi:file-delimited').
        file_extension: File extension for exported files (e.g., '.json', '.md').
                        Should include the leading dot.
        mime_type: MIME type for HTTP responses (e.g., 'application/json', 'text/csv').
        path_setting_key: Configuration key for export path setting (e.g., 'export_path',
                          'vault_path'). Used to identify which config field contains
                          the export destination path.
        ui_color: Hex color code for UI theming (e.g., '#F7DF1E').
                  Used for visual identification in the UI. None if no color defined.
        requires_connection: Whether the exporter requires a Connection entity for
                             credentials. If True, export destinations using this
                             exporter must have a connection_id set.
        connection_types: List of supported connection types (e.g., ['http_basic', 'api_key']).
                          Empty list means any connection type is acceptable.
                          Only relevant if requires_connection is True.

    Example:
        >>> metadata = ExporterMetadata(
        ...     name="obsidian",
        ...     display_name="Obsidian",
        ...     description="Export digests to Obsidian vault with frontmatter",
        ...     icon="simple-icons:obsidian",
        ...     file_extension=".md",
        ...     mime_type="text/markdown",
        ...     path_setting_key="vault_path",
        ...     ui_color="#7C3AED",
        ... )
    """

    file_extension: str = ''
    mime_type: str = 'application/octet-stream'
    path_setting_key: str = 'export_path'
    ui_color: str | None = None
    requires_connection: bool = False
    connection_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for API responses.

        Extends the base to_dict() to include all exporter-specific fields.

        Returns:
            Dictionary with all metadata fields serialized.
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "file_extension": self.file_extension,
            "mime_type": self.mime_type,
            "path_setting_key": self.path_setting_key,
            "ui_color": self.ui_color,
            "requires_connection": self.requires_connection,
            "connection_types": self.connection_types,
        }
