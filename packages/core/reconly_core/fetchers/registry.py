"""Fetcher registry for self-registering fetchers."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Type

if TYPE_CHECKING:
    from reconly_core.extensions.types import ExtensionMetadata
    from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema

logger = logging.getLogger(__name__)


@dataclass
class FetcherRegistryEntry:
    """Entry in the fetcher registry with extension metadata."""
    cls: Type[BaseFetcher]
    is_extension: bool = False
    metadata: Optional[ExtensionMetadata] = None
    config_schema: Optional[FetcherConfigSchema] = None


# Global registry of source type -> fetcher entry
_FETCHER_REGISTRY: Dict[str, FetcherRegistryEntry] = {}


def register_fetcher(name: str, is_extension: bool = False, metadata: Optional[ExtensionMetadata] = None):
    """
    Decorator to register a fetcher class in the global registry.

    Contributors can use this decorator to make their fetcher automatically
    discoverable without modifying factory.py.

    Args:
        name: Source type name (e.g., 'rss', 'youtube', 'website')
        is_extension: Whether this is an external extension (default False)
        metadata: Extension metadata if this is an extension

    Returns:
        Decorator function that registers the class

    Example:
        >>> @register_fetcher('rss')
        >>> class RSSFetcher(BaseFetcher):
        >>>     ...
    """
    def decorator(cls: Type[BaseFetcher]):
        # Import here to avoid circular dependency
        from reconly_core.fetchers.base import BaseFetcher

        # Validate that class inherits from BaseFetcher
        if not issubclass(cls, BaseFetcher):
            raise TypeError(
                f"{cls.__name__} must inherit from BaseFetcher to be registered as a fetcher"
            )

        # Warn if overriding existing fetcher
        if name in _FETCHER_REGISTRY:
            existing = _FETCHER_REGISTRY[name]
            logger.warning(
                f"Fetcher '{name}' is already registered as {existing.cls.__name__}. "
                f"Overriding with {cls.__name__}."
            )

        # Get config schema from instance and register in one pass
        config_schema = None
        try:
            instance = cls()
            config_schema = instance.get_config_schema()
            _register_fetcher_settings(name, config_schema)
        except Exception as e:
            logger.warning(f"Failed to get config schema for fetcher '{name}': {e}")

        _FETCHER_REGISTRY[name] = FetcherRegistryEntry(
            cls=cls,
            is_extension=is_extension,
            metadata=metadata,
            config_schema=config_schema,
        )
        logger.debug(f"Registered fetcher '{name}' -> {cls.__name__} (extension={is_extension})")

        return cls

    return decorator


def _register_fetcher_settings(name: str, config_schema: FetcherConfigSchema) -> None:
    """Register settings for a fetcher based on its config schema.

    Uses a direct module import to avoid circular dependency through
    services/__init__.py -> digest_service -> fetchers.

    Always registers the enabled setting, even for fetchers with no config fields.
    """
    import importlib

    try:
        settings_registry = importlib.import_module(
            'reconly_core.services.settings_registry'
        )
        settings_registry.register_component_settings("fetch", name, config_schema)
        logger.debug(f"Auto-registered settings for fetcher '{name}'")
    except Exception as e:
        logger.warning(f"Failed to auto-register settings for fetcher '{name}': {e}")


def get_fetcher_class(name: str) -> Type[BaseFetcher]:
    """
    Get a fetcher class by source type name.

    Args:
        name: Source type name (e.g., 'rss', 'youtube')

    Returns:
        Fetcher class (not instantiated)

    Raises:
        ValueError: If source type is not registered

    Example:
        >>> RSSFetcherClass = get_fetcher_class('rss')
        >>> fetcher = RSSFetcherClass()
    """
    if name not in _FETCHER_REGISTRY:
        available = list(_FETCHER_REGISTRY.keys())
        raise ValueError(
            f"Unknown source type '{name}'. "
            f"Available types: {available}. "
            f"See docs/ADDING_FETCHERS.md for information on adding new fetchers."
        )

    return _FETCHER_REGISTRY[name].cls


def get_fetcher_entry(name: str) -> FetcherRegistryEntry:
    """
    Get the full registry entry for a fetcher.

    Args:
        name: Source type name (e.g., 'rss', 'youtube')

    Returns:
        FetcherRegistryEntry with class and extension info

    Raises:
        ValueError: If source type is not registered
    """
    if name not in _FETCHER_REGISTRY:
        available = list(_FETCHER_REGISTRY.keys())
        raise ValueError(
            f"Unknown source type '{name}'. "
            f"Available types: {available}."
        )

    return _FETCHER_REGISTRY[name]


def is_fetcher_extension(name: str) -> bool:
    """
    Check if a fetcher is an external extension.

    Args:
        name: Source type to check

    Returns:
        True if fetcher is an extension, False if built-in or not found
    """
    if name not in _FETCHER_REGISTRY:
        return False
    return _FETCHER_REGISTRY[name].is_extension


def list_fetchers() -> List[str]:
    """
    List all registered fetcher source types.

    Returns:
        List of source types (e.g., ['rss', 'youtube', 'website'])

    Example:
        >>> list_fetchers()
        ['rss', 'youtube', 'website']
    """
    return list(_FETCHER_REGISTRY.keys())


def list_extension_fetchers() -> List[str]:
    """
    List only external extension fetchers.

    Returns:
        List of extension fetcher source types

    Example:
        >>> list_extension_fetchers()
        ['reddit', 'twitter']
    """
    return [
        name for name, entry in _FETCHER_REGISTRY.items()
        if entry.is_extension
    ]


def list_builtin_fetchers() -> List[str]:
    """
    List only built-in (non-extension) fetchers.

    Returns:
        List of built-in fetcher source types

    Example:
        >>> list_builtin_fetchers()
        ['rss', 'youtube', 'website']
    """
    return [
        name for name, entry in _FETCHER_REGISTRY.items()
        if not entry.is_extension
    ]


def is_fetcher_registered(name: str) -> bool:
    """
    Check if a fetcher is registered.

    Args:
        name: Source type to check

    Returns:
        True if fetcher is registered, False otherwise
    """
    return name in _FETCHER_REGISTRY


def get_extension_info(name: str) -> Optional[Dict]:
    """
    Get extension information for a fetcher if it's an extension.

    Args:
        name: Source type

    Returns:
        Dict with extension info if fetcher is an extension, None otherwise
    """
    if name not in _FETCHER_REGISTRY:
        return None

    entry = _FETCHER_REGISTRY[name]
    if not entry.is_extension:
        return None

    return {
        "name": name,
        "is_extension": True,
        "metadata": entry.metadata.to_dict() if entry.metadata else None,
    }


def detect_fetcher(url: str) -> Optional[BaseFetcher]:
    """
    Auto-detect appropriate fetcher for a URL.

    Iterates through registered fetchers and returns the first one
    that can handle the URL (based on can_handle() method).

    Args:
        url: URL to check

    Returns:
        Fetcher instance if one can handle the URL, None otherwise

    Example:
        >>> fetcher = detect_fetcher('https://www.youtube.com/channel/UC...')
        >>> if fetcher:
        >>>     items = fetcher.fetch(url)
    """
    for entry in _FETCHER_REGISTRY.values():
        try:
            fetcher = entry.cls()
            if fetcher.can_handle(url):
                return fetcher
        except Exception:
            continue
    return None
