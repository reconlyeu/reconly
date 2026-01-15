"""Extension loading system for Reconly.

This module provides infrastructure for loading external extensions
(exporters, fetchers, providers) from installed packages using
Python entry points (PEP 621).

Extension authors can create extensions by:
1. Creating a package with entry points in pyproject.toml
2. Using @register_exporter/@register_fetcher decorators
3. Adding __extension_*__ class attributes for metadata

Example pyproject.toml:
    [project.entry-points."reconly.exporters"]
    notion = "reconly_ext_notion:NotionExporter"

Example extension class:
    @register_exporter('notion')
    class NotionExporter(BaseExporter):
        __extension_name__ = "Notion Exporter"
        __extension_version__ = "1.0.0"
        __extension_author__ = "Community"
        __extension_min_reconly__ = "0.5.0"
        __extension_description__ = "Export digests to Notion"
        ...
"""
from reconly_core.extensions.types import (
    ExtensionType,
    ExtensionMetadata,
    ExtensionInfo,
    LoadedExtension,
    ExtensionLoadResult,
)
from reconly_core.extensions.loader import (
    ExtensionLoader,
    get_extension_loader,
    load_extensions,
    extract_extension_metadata,
    validate_extension_compatibility,
    get_reconly_version,
    ENTRY_POINT_GROUPS,
)
from reconly_core.extensions.settings import (
    get_extension_settings_prefix,
    get_extension_enabled_key,
    is_extension_enabled,
    is_extension_configured,
    can_enable_extension,
    set_extension_enabled,
    get_extension_activation_state,
    register_extension_settings,
)
from reconly_core.extensions.installer import (
    ExtensionInstaller,
    InstallResult,
    get_extension_installer,
    EXTENSION_PACKAGE_PREFIX,
    GITHUB_HTTPS_PREFIX,
    GITHUB_SSH_PREFIX,
)
from reconly_core.extensions.catalog import (
    CatalogEntry,
    Catalog,
    CatalogFetcher,
    InstallSource,
    get_catalog_fetcher,
    fetch_catalog,
    fetch_catalog_sync,
    search_catalog,
)


def ensure_extensions_loaded():
    """Ensure all extension types are loaded.

    Call this before accessing extension data to ensure extensions
    have been discovered and registered. This is called lazily by
    the factory modules, but can be called explicitly when needed.
    """
    # Import factories which will trigger lazy loading
    from reconly_core.exporters.factory import _load_exporter_extensions
    from reconly_core.fetchers.factory import _load_fetcher_extensions

    _load_exporter_extensions()
    _load_fetcher_extensions()


__all__ = [
    # Types
    "ExtensionType",
    "ExtensionMetadata",
    "ExtensionInfo",
    "LoadedExtension",
    "ExtensionLoadResult",
    # Loader
    "ExtensionLoader",
    "get_extension_loader",
    "load_extensions",
    "extract_extension_metadata",
    "validate_extension_compatibility",
    "get_reconly_version",
    "ENTRY_POINT_GROUPS",
    # Settings
    "get_extension_settings_prefix",
    "get_extension_enabled_key",
    "is_extension_enabled",
    "is_extension_configured",
    "can_enable_extension",
    "set_extension_enabled",
    "get_extension_activation_state",
    "register_extension_settings",
    # Installer
    "ExtensionInstaller",
    "InstallResult",
    "get_extension_installer",
    "EXTENSION_PACKAGE_PREFIX",
    "GITHUB_HTTPS_PREFIX",
    "GITHUB_SSH_PREFIX",
    # Catalog
    "CatalogEntry",
    "Catalog",
    "CatalogFetcher",
    "InstallSource",
    "get_catalog_fetcher",
    "fetch_catalog",
    "fetch_catalog_sync",
    "search_catalog",
    # Helpers
    "ensure_extensions_loaded",
]
