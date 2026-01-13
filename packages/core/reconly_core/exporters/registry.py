"""Exporter registry for self-registering exporters."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.exporters.base import BaseExporter
    from reconly_core.extensions.types import ExtensionMetadata

logger = logging.getLogger(__name__)


@dataclass
class ExporterRegistryEntry:
    """Entry in the exporter registry with extension metadata."""
    cls: type[BaseExporter]
    is_extension: bool = False
    metadata: ExtensionMetadata | None = None


# Global registry of format name -> exporter entry
_EXPORTER_REGISTRY: dict[str, ExporterRegistryEntry] = {}


def register_exporter(
    name: str,
    is_extension: bool = False,
    metadata: ExtensionMetadata | None = None,
):
    """
    Decorator to register an exporter class in the global registry.

    Contributors can use this decorator to make their exporter automatically
    discoverable without modifying factory.py.

    Args:
        name: Format name (e.g., 'json', 'csv', 'obsidian')
        is_extension: Whether this is an external extension (default False)
        metadata: Extension metadata if this is an extension

    Returns:
        Decorator function that registers the class

    Example:
        >>> @register_exporter('json')
        >>> class JSONExporter(BaseExporter):
        >>>     ...
    """
    def decorator(cls: type[BaseExporter]) -> type[BaseExporter]:
        from reconly_core.exporters.base import BaseExporter

        if not issubclass(cls, BaseExporter):
            raise TypeError(
                f"{cls.__name__} must inherit from BaseExporter to be registered"
            )

        if name in _EXPORTER_REGISTRY:
            existing = _EXPORTER_REGISTRY[name]
            logger.warning(
                f"Exporter '{name}' already registered as {existing.cls.__name__}, "
                f"overriding with {cls.__name__}"
            )

        _EXPORTER_REGISTRY[name] = ExporterRegistryEntry(
            cls=cls,
            is_extension=is_extension,
            metadata=metadata,
        )
        logger.debug(f"Registered exporter '{name}' -> {cls.__name__}")

        # Auto-register settings from the exporter's config schema
        _register_exporter_settings(name, cls)

        return cls

    return decorator


def _register_exporter_settings(name: str, cls: type[BaseExporter]) -> None:
    """Register settings for an exporter based on its config schema."""
    from reconly_core.services.settings_registry import register_component_settings

    try:
        config_schema = cls().get_config_schema()
        if config_schema.fields:
            register_component_settings("export", name, config_schema)
            logger.debug(f"Auto-registered settings for exporter '{name}'")
    except Exception as e:
        logger.warning(f"Failed to auto-register settings for exporter '{name}': {e}")


def get_exporter_class(name: str) -> type[BaseExporter]:
    """
    Get an exporter class by format name.

    Args:
        name: Format name (e.g., 'json', 'csv')

    Returns:
        Exporter class (not instantiated)

    Raises:
        ValueError: If format name is not registered

    Example:
        >>> JSONExporterClass = get_exporter_class('json')
        >>> exporter = JSONExporterClass()
    """
    if name not in _EXPORTER_REGISTRY:
        available = list(_EXPORTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown export format '{name}'. "
            f"Available formats: {available}. "
            f"See docs/ADDING_EXPORTERS.md for adding new exporters."
        )

    return _EXPORTER_REGISTRY[name].cls


def get_exporter_entry(name: str) -> ExporterRegistryEntry:
    """
    Get the full registry entry for an exporter.

    Args:
        name: Format name (e.g., 'json', 'csv')

    Returns:
        ExporterRegistryEntry with class and extension info

    Raises:
        ValueError: If format name is not registered
    """
    if name not in _EXPORTER_REGISTRY:
        available = list(_EXPORTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown export format '{name}'. "
            f"Available formats: {available}."
        )

    return _EXPORTER_REGISTRY[name]


def is_exporter_extension(name: str) -> bool:
    """
    Check if an exporter is an external extension.

    Args:
        name: Format name to check

    Returns:
        True if exporter is an extension, False if built-in or not found
    """
    if name not in _EXPORTER_REGISTRY:
        return False
    return _EXPORTER_REGISTRY[name].is_extension


def list_exporters() -> list[str]:
    """List all registered exporter format names."""
    return list(_EXPORTER_REGISTRY.keys())


def list_extension_exporters() -> list[str]:
    """List only external extension exporters."""
    return [
        name for name, entry in _EXPORTER_REGISTRY.items()
        if entry.is_extension
    ]


def list_builtin_exporters() -> list[str]:
    """List only built-in (non-extension) exporters."""
    return [
        name for name, entry in _EXPORTER_REGISTRY.items()
        if not entry.is_extension
    ]


def is_exporter_registered(name: str) -> bool:
    """
    Check if an exporter is registered.

    Args:
        name: Format name to check

    Returns:
        True if exporter is registered, False otherwise
    """
    return name in _EXPORTER_REGISTRY


def get_extension_info(name: str) -> dict | None:
    """
    Get extension information for an exporter if it's an extension.

    Args:
        name: Format name

    Returns:
        Dict with extension info if exporter is an extension, None otherwise
    """
    if name not in _EXPORTER_REGISTRY:
        return None

    entry = _EXPORTER_REGISTRY[name]
    if not entry.is_extension:
        return None

    return {
        "name": name,
        "is_extension": True,
        "metadata": entry.metadata.to_dict() if entry.metadata else None,
    }
