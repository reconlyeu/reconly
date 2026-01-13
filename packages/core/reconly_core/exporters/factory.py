"""Exporter factory for getting exporter instances."""
import logging
from typing import Any, Dict, List

from reconly_core.exporters.base import BaseExporter, ExportResult
from reconly_core.exporters.registry import (
    get_exporter_class,
    get_exporter_entry,
    list_exporters,
    list_extension_exporters,
    is_exporter_registered,
    is_exporter_extension,
    register_exporter,
)

logger = logging.getLogger(__name__)

# Import exporters to ensure they're registered
from reconly_core.exporters import json_exporter  # noqa: F401
from reconly_core.exporters import csv_exporter  # noqa: F401
from reconly_core.exporters import markdown  # noqa: F401

# Track whether extensions have been loaded (lazy loading to avoid circular imports)
_extensions_loaded = False


def _load_exporter_extensions():
    """Load external exporter extensions from entry points.

    This is called lazily to avoid circular imports when extensions
    import from reconly_core.exporters.base.
    """
    global _extensions_loaded
    if _extensions_loaded:
        return
    _extensions_loaded = True

    try:
        from reconly_core.extensions import (
            ExtensionLoader,
            ExtensionType,
        )

        loader = ExtensionLoader()
        result = loader.load_extensions_for_type(ExtensionType.EXPORTER)

        # Register each loaded extension
        for ext in result.loaded:
            # The extension class already has @register_exporter decorator,
            # but we need to mark it as an extension with metadata
            register_exporter(
                ext.entry_point_name,
                is_extension=True,
                metadata=ext.metadata
            )(ext.cls)

        if result.errors:
            for name, error in result.errors.items():
                logger.warning(f"Failed to load exporter extension '{name}': {error}")

    except ImportError:
        # Extensions module not available - skip
        pass
    except Exception as e:
        logger.warning(f"Error loading exporter extensions: {e}")


def get_exporter(format_name: str) -> BaseExporter:
    """
    Get an exporter instance by format name.

    Args:
        format_name: Format name (e.g., 'json', 'csv', 'obsidian')

    Returns:
        BaseExporter instance ready for export

    Raises:
        ValueError: If format name is not registered

    Example:
        >>> exporter = get_exporter('json')
        >>> result = exporter.export(digests)
    """
    _load_exporter_extensions()  # Ensure extensions are loaded
    exporter_class = get_exporter_class(format_name)
    return exporter_class()


def export_digests(
    digests: List[Any],
    format_name: str,
    config: Dict[str, Any] = None
) -> ExportResult:
    """
    Export digests to the specified format.

    Convenience function that gets an exporter and calls export in one step.

    Args:
        digests: List of Digest model instances
        format_name: Format name (e.g., 'json', 'csv', 'obsidian')
        config: Optional export configuration

    Returns:
        ExportResult with content and metadata

    Example:
        >>> result = export_digests(digests, 'json')
        >>> print(result.content)
    """
    exporter = get_exporter(format_name)
    return exporter.export(digests, config)


def get_available_formats() -> List[Dict[str, str]]:
    """
    Get information about all available export formats.

    Returns:
        List of dicts with format details (name, content_type, extension, description)

    Example:
        >>> get_available_formats()
        [{'name': 'json', 'content_type': 'application/json', ...}, ...]
    """
    _load_exporter_extensions()  # Ensure extensions are loaded
    formats = []
    for format_name in list_exporters():
        try:
            exporter = get_exporter(format_name)
            formats.append({
                'name': format_name,
                'content_type': exporter.get_content_type(),
                'extension': exporter.get_file_extension(),
                'description': exporter.get_description(),
            })
        except Exception:
            continue
    return formats


__all__ = [
    'get_exporter',
    'export_digests',
    'list_exporters',
    'list_extension_exporters',
    'is_exporter_registered',
    'is_exporter_extension',
    'get_exporter_entry',
    'get_available_formats',
    'BaseExporter',
    'ExportResult',
]
