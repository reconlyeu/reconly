"""Extension loader using Python entry points.

This module handles discovery and loading of external extensions from
installed packages using PEP 621 entry points.
"""
import logging
from importlib.metadata import entry_points, version as get_version
from typing import Dict, List, Optional, Type

from reconly_core.extensions.types import (
    ExtensionType,
    ExtensionMetadata,
    LoadedExtension,
    ExtensionLoadResult,
)

logger = logging.getLogger(__name__)

# Entry point group names
ENTRY_POINT_GROUPS = {
    ExtensionType.EXPORTER: "reconly.exporters",
    ExtensionType.FETCHER: "reconly.fetchers",
    ExtensionType.PROVIDER: "reconly.providers",
}


def get_reconly_version() -> str:
    """Get the current Reconly version.

    Returns:
        Version string, or "0.0.0" if not determinable.
    """
    try:
        return get_version("reconly-core")
    except Exception:
        return "0.0.0"


def parse_version(version_str: str) -> tuple:
    """Parse a version string into comparable tuple.

    Args:
        version_str: Version string like "1.0.0" or "1.0.0-beta"

    Returns:
        Tuple of integers for comparison (ignores pre-release suffixes)
    """
    # Strip any pre-release suffix
    base_version = version_str.split("-")[0].split("+")[0]
    parts = base_version.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return (0, 0, 0)


def validate_extension_compatibility(
    min_version: str,
    current_version: Optional[str] = None
) -> bool:
    """Check if extension is compatible with current Reconly version.

    Args:
        min_version: Minimum required Reconly version (from extension)
        current_version: Current Reconly version (auto-detected if None)

    Returns:
        True if compatible, False otherwise.
    """
    if current_version is None:
        current_version = get_reconly_version()

    current_tuple = parse_version(current_version)
    min_tuple = parse_version(min_version)

    return current_tuple >= min_tuple


def extract_extension_metadata(
    cls: type,
    extension_type: ExtensionType,
    registry_name: str
) -> ExtensionMetadata:
    """Extract metadata from extension class attributes.

    Extension authors should define these attributes:
        __extension_name__ = "My Extension"
        __extension_version__ = "1.0.0"
        __extension_author__ = "Author Name"
        __extension_min_reconly__ = "0.5.0"
        __extension_description__ = "Description"
        __extension_homepage__ = "https://..."

    Args:
        cls: Extension class
        extension_type: Type of extension
        registry_name: Name used in registry

    Returns:
        ExtensionMetadata with extracted values (defaults for missing attrs)
    """
    return ExtensionMetadata(
        name=getattr(cls, "__extension_name__", cls.__name__),
        version=getattr(cls, "__extension_version__", "0.0.0"),
        author=getattr(cls, "__extension_author__", "Unknown"),
        min_reconly=getattr(cls, "__extension_min_reconly__", "0.0.0"),
        description=getattr(
            cls,
            "__extension_description__",
            f"{extension_type.value.title()} extension"
        ),
        homepage=getattr(cls, "__extension_homepage__", None),
        extension_type=extension_type,
        registry_name=registry_name,
    )


def _get_base_class_for_type(extension_type: ExtensionType) -> Type:
    """Get the base class that extensions of this type must inherit from.

    Args:
        extension_type: Type of extension

    Returns:
        Base class (e.g., BaseExporter, BaseFetcher)

    Raises:
        ValueError: If extension type is unknown
    """
    if extension_type == ExtensionType.EXPORTER:
        from reconly_core.exporters.base import BaseExporter
        return BaseExporter
    elif extension_type == ExtensionType.FETCHER:
        from reconly_core.fetchers.base import BaseFetcher
        return BaseFetcher
    elif extension_type == ExtensionType.PROVIDER:
        # Providers don't have a base class yet - use object
        # TODO: Add BaseProvider when implementing provider extensions
        return object
    else:
        raise ValueError(f"Unknown extension type: {extension_type}")


class ExtensionLoader:
    """Loader for discovering and loading extensions via entry points.

    Usage:
        loader = ExtensionLoader()
        result = loader.load_all()
        for ext in result.loaded:
            print(f"Loaded: {ext.metadata.name}")
    """

    def __init__(self):
        """Initialize the extension loader."""
        self._loaded_extensions: Dict[str, LoadedExtension] = {}
        self._load_errors: Dict[str, str] = {}

    def discover_extensions(
        self,
        extension_type: ExtensionType
    ) -> List[str]:
        """Discover available extensions for a type.

        Args:
            extension_type: Type of extensions to discover

        Returns:
            List of entry point names available for this type
        """
        group = ENTRY_POINT_GROUPS.get(extension_type)
        if not group:
            return []

        try:
            # Python 3.10+ entry_points() returns SelectableGroups
            eps = entry_points(group=group)
            return [ep.name for ep in eps]
        except TypeError:
            # Python 3.9 compatibility
            all_eps = entry_points()
            if hasattr(all_eps, "get"):
                return [ep.name for ep in all_eps.get(group, [])]
            return []

    def load_extension(
        self,
        extension_type: ExtensionType,
        name: str
    ) -> Optional[LoadedExtension]:
        """Load a single extension by name.

        Args:
            extension_type: Type of extension
            name: Entry point name (e.g., 'notion')

        Returns:
            LoadedExtension if successful, None otherwise
        """
        group = ENTRY_POINT_GROUPS.get(extension_type)
        if not group:
            self._load_errors[name] = f"Unknown extension type: {extension_type}"
            return None

        try:
            # Find the entry point
            eps = entry_points(group=group)
            ep = None
            for candidate in eps:
                if candidate.name == name:
                    ep = candidate
                    break

            if ep is None:
                self._load_errors[name] = f"Entry point '{name}' not found in {group}"
                return None

            # Load the class
            cls = ep.load()

            # Validate base class
            base_class = _get_base_class_for_type(extension_type)
            if not issubclass(cls, base_class):
                self._load_errors[name] = (
                    f"{cls.__name__} must inherit from {base_class.__name__}"
                )
                return None

            # Extract metadata
            metadata = extract_extension_metadata(cls, extension_type, name)

            # Check version compatibility
            if not validate_extension_compatibility(metadata.min_reconly):
                current = get_reconly_version()
                self._load_errors[name] = (
                    f"Requires Reconly {metadata.min_reconly}+, "
                    f"current version is {current}"
                )
                return None

            loaded = LoadedExtension(
                cls=cls,
                metadata=metadata,
                entry_point_name=name,
                entry_point_group=group,
            )
            self._loaded_extensions[f"{group}:{name}"] = loaded

            logger.info(
                f"Loaded extension: {metadata.name} v{metadata.version} "
                f"({extension_type.value}: {name})"
            )
            return loaded

        except Exception as e:
            error_msg = f"Failed to load extension '{name}': {str(e)}"
            self._load_errors[name] = error_msg
            logger.warning(error_msg)
            return None

    def load_extensions_for_type(
        self,
        extension_type: ExtensionType
    ) -> ExtensionLoadResult:
        """Load all extensions of a specific type.

        Args:
            extension_type: Type of extensions to load

        Returns:
            ExtensionLoadResult with loaded extensions and errors
        """
        result = ExtensionLoadResult()

        names = self.discover_extensions(extension_type)
        for name in names:
            loaded = self.load_extension(extension_type, name)
            if loaded:
                result.loaded.append(loaded)
            elif name in self._load_errors:
                result.errors[name] = self._load_errors[name]

        return result

    def load_all(self) -> ExtensionLoadResult:
        """Load all extensions of all types.

        Returns:
            Combined ExtensionLoadResult for all extension types
        """
        result = ExtensionLoadResult()

        for ext_type in ExtensionType:
            type_result = self.load_extensions_for_type(ext_type)
            result.loaded.extend(type_result.loaded)
            result.errors.update(type_result.errors)

        if result.loaded:
            summary = ", ".join(
                f"{ext.metadata.name} ({ext.metadata.extension_type.value})"
                for ext in result.loaded
            )
            logger.info(f"Loaded {len(result.loaded)} extension(s): {summary}")

        if result.errors:
            logger.warning(
                f"Failed to load {len(result.errors)} extension(s): "
                f"{list(result.errors.keys())}"
            )

        return result

    def get_loaded_extensions(self) -> Dict[str, LoadedExtension]:
        """Get all loaded extensions.

        Returns:
            Dict mapping "group:name" to LoadedExtension
        """
        return self._loaded_extensions.copy()

    def get_load_errors(self) -> Dict[str, str]:
        """Get all load errors.

        Returns:
            Dict mapping entry point name to error message
        """
        return self._load_errors.copy()


# Module-level singleton for convenience
_loader: Optional[ExtensionLoader] = None


def get_extension_loader() -> ExtensionLoader:
    """Get the global extension loader singleton.

    Returns:
        ExtensionLoader instance
    """
    global _loader
    if _loader is None:
        _loader = ExtensionLoader()
    return _loader


def load_extensions() -> ExtensionLoadResult:
    """Load all extensions using the global loader.

    This is the main entry point for loading extensions at startup.

    Returns:
        ExtensionLoadResult with all loaded extensions and errors
    """
    return get_extension_loader().load_all()
