"""Extension types and dataclasses.

This module defines the data structures for extension metadata and information.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ExtensionType(str, Enum):
    """Types of extensions that can be loaded."""
    EXPORTER = "exporter"
    FETCHER = "fetcher"
    PROVIDER = "provider"


@dataclass
class ExtensionMetadata:
    """Metadata for an extension, extracted from class attributes.

    Extension authors should define these as class attributes:
        __extension_name__ = "My Extension"
        __extension_version__ = "1.0.0"
        __extension_author__ = "Author Name"
        __extension_min_reconly__ = "0.5.0"
        __extension_description__ = "What this extension does"
        __extension_homepage__ = "https://github.com/..."

    Attributes:
        name: Human-readable name of the extension
        version: Extension version string (semver recommended)
        author: Author name or organization
        min_reconly: Minimum Reconly version required
        description: Brief description of extension functionality
        homepage: URL to extension homepage or repository
        extension_type: Type of extension (exporter, fetcher, provider)
        registry_name: Name used in registry (e.g., 'notion' for NotionExporter)
    """
    name: str
    version: str
    author: str
    min_reconly: str
    description: str
    extension_type: ExtensionType
    registry_name: str
    homepage: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "min_reconly": self.min_reconly,
            "description": self.description,
            "homepage": self.homepage,
            "type": self.extension_type.value,
            "registry_name": self.registry_name,
        }


@dataclass
class ExtensionInfo:
    """Complete information about an installed extension.

    Combines metadata with runtime status information.

    Attributes:
        metadata: Extension metadata from class attributes
        is_extension: Always True for extensions (False for built-ins)
        enabled: Whether extension is currently enabled
        is_configured: Whether all required config fields have values
        can_enable: Whether extension can be enabled (configured or no required fields)
        load_error: Error message if extension failed to load
    """
    metadata: ExtensionMetadata
    is_extension: bool = True
    enabled: bool = False
    is_configured: bool = True
    can_enable: bool = True
    load_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            **self.metadata.to_dict(),
            "is_extension": self.is_extension,
            "enabled": self.enabled,
            "is_configured": self.is_configured,
            "can_enable": self.can_enable,
            "load_error": self.load_error,
        }


@dataclass
class LoadedExtension:
    """An extension that was successfully loaded.

    Attributes:
        cls: The extension class
        metadata: Extracted metadata
        entry_point_name: Name from entry point (e.g., 'notion')
        entry_point_group: Entry point group (e.g., 'reconly.exporters')
    """
    cls: type
    metadata: ExtensionMetadata
    entry_point_name: str
    entry_point_group: str


@dataclass
class ExtensionLoadResult:
    """Result of attempting to load extensions.

    Attributes:
        loaded: Successfully loaded extensions
        errors: Mapping of entry point name to error message
    """
    loaded: List[LoadedExtension] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
