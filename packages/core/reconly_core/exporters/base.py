"""Base exporter interface.

This module defines the abstract base class for all digest exporters.
Exporters transform Digest objects into various output formats (JSON, CSV, Markdown, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from reconly_core.config_types import ConfigField, ComponentConfigSchema


# Re-export ConfigField for backwards compatibility
__all__ = ["ConfigField", "ExporterConfigSchema", "ExportToPathResult", "ExportResult", "BaseExporter"]


@dataclass
class ExporterConfigSchema(ComponentConfigSchema):
    """Configuration schema for an exporter.

    Inherits fields from ComponentConfigSchema.

    Attributes:
        supports_direct_export: Whether exporter can write to filesystem
    """
    supports_direct_export: bool = False


@dataclass
class ExportToPathResult:
    """Result of an export-to-path operation.

    Attributes:
        success: Whether all files were written successfully
        files_written: Number of files successfully written
        files_skipped: Number of files skipped (already exist)
        target_path: Directory where files were written
        filenames: List of written filenames
        errors: List of error details for failed writes
    """
    success: bool
    files_written: int
    target_path: str
    filenames: List[str] = field(default_factory=list)
    files_skipped: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ExportResult:
    """Result of an export operation.

    Attributes:
        content: The exported content (string for text formats, bytes for binary)
        filename: Suggested filename for downloads
        content_type: MIME type for HTTP response
        digest_count: Number of digests exported
    """
    content: Union[str, bytes]
    filename: str
    content_type: str
    digest_count: int


class BaseExporter(ABC):
    """Abstract base class for digest exporters.

    Subclasses must implement all abstract methods to provide format-specific
    export functionality.

    Example:
        >>> @register_exporter('json')
        >>> class JSONExporter(BaseExporter):
        >>>     def export(self, digests, config=None):
        >>>         # Export logic here
        >>>         return ExportResult(...)
    """

    @abstractmethod
    def export(
        self,
        digests: List[Any],
        config: Dict[str, Any] = None
    ) -> ExportResult:
        """
        Export digests to this format.

        Args:
            digests: List of Digest model instances
            config: Optional export configuration (format-specific options)

        Returns:
            ExportResult with content and metadata
        """
        pass

    @abstractmethod
    def get_format_name(self) -> str:
        """
        Get the unique format identifier.

        Returns:
            Format name (e.g., 'json', 'csv', 'obsidian')
        """
        pass

    @abstractmethod
    def get_content_type(self) -> str:
        """
        Get the MIME type for HTTP response.

        Returns:
            MIME type (e.g., 'application/json', 'text/csv')
        """
        pass

    @abstractmethod
    def get_file_extension(self) -> str:
        """
        Get the file extension for downloads.

        Returns:
            Extension without dot (e.g., 'json', 'csv', 'md')
        """
        pass

    def get_description(self) -> str:
        """
        Get a human-readable description of this format.

        Returns:
            Description string
        """
        return f"{self.get_format_name().upper()} format"

    def get_config_schema(self) -> ExporterConfigSchema:
        """
        Get the configuration schema for this exporter.

        Override this method in subclasses to declare configurable settings.
        The default implementation returns an empty schema with no fields
        and supports_direct_export=False.

        Returns:
            ExporterConfigSchema with field definitions
        """
        return ExporterConfigSchema(fields=[], supports_direct_export=False)

    def export_to_path(
        self,
        digests: List[Any],
        base_path: str,
        config: Optional[Dict[str, Any]] = None
    ) -> ExportToPathResult:
        """
        Export digests directly to the filesystem.

        Override this method in subclasses that support direct file export.
        The default implementation raises NotImplementedError.

        Args:
            digests: List of Digest model instances
            base_path: Base directory path to write files to
            config: Exporter-specific configuration options

        Returns:
            ExportToPathResult with written files and any errors

        Raises:
            NotImplementedError: If exporter doesn't support direct export
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support direct file export. "
            f"Use export() method instead."
        )
