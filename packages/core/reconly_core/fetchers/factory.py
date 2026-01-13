"""Fetcher factory for getting fetcher instances."""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from reconly_core.fetchers.base import BaseFetcher, FetchedItem
from reconly_core.fetchers.registry import (
    get_fetcher_class,
    get_fetcher_entry,
    list_fetchers,
    list_extension_fetchers,
    is_fetcher_registered,
    is_fetcher_extension,
    detect_fetcher,
    register_fetcher,
)

logger = logging.getLogger(__name__)

# Import fetchers to ensure they're registered
from reconly_core.fetchers import rss  # noqa: F401
from reconly_core.fetchers import youtube  # noqa: F401
from reconly_core.fetchers import website  # noqa: F401
from reconly_core.fetchers import agent  # noqa: F401

# Track whether extensions have been loaded (lazy loading to avoid circular imports)
_extensions_loaded = False


def _load_fetcher_extensions():
    """Load external fetcher extensions from entry points.

    This is called lazily to avoid circular imports when extensions
    import from reconly_core.fetchers.base.
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
        result = loader.load_extensions_for_type(ExtensionType.FETCHER)

        # Register each loaded extension
        for ext in result.loaded:
            # The extension class already has @register_fetcher decorator,
            # but we need to mark it as an extension with metadata
            register_fetcher(
                ext.entry_point_name,
                is_extension=True,
                metadata=ext.metadata
            )(ext.cls)

        if result.errors:
            for name, error in result.errors.items():
                logger.warning(f"Failed to load fetcher extension '{name}': {error}")

    except ImportError:
        # Extensions module not available - skip
        pass
    except Exception as e:
        logger.warning(f"Error loading fetcher extensions: {e}")


def get_fetcher(source_type: str) -> BaseFetcher:
    """
    Get a fetcher instance by source type.

    Args:
        source_type: Source type (e.g., 'rss', 'youtube', 'website')

    Returns:
        BaseFetcher instance ready for fetching

    Raises:
        ValueError: If source type is not registered

    Example:
        >>> fetcher = get_fetcher('rss')
        >>> items = fetcher.fetch(url, since=since)
    """
    _load_fetcher_extensions()  # Ensure extensions are loaded
    fetcher_class = get_fetcher_class(source_type)
    return fetcher_class()


def fetch_content(
    url: str,
    source_type: str,
    since: Optional[datetime] = None,
    max_items: Optional[int] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Fetch content from a URL using the specified source type.

    Convenience function that gets a fetcher and calls fetch in one step.

    Args:
        url: Source URL
        source_type: Source type (e.g., 'rss', 'youtube', 'website')
        since: Only return items published after this datetime
        max_items: Maximum number of items to return

    Returns:
        List of item dictionaries

    Example:
        >>> items = fetch_content(url, 'rss', since=since)
    """
    fetcher = get_fetcher(source_type)
    return fetcher.fetch(url, since=since, max_items=max_items, **kwargs)


def get_available_fetchers() -> List[Dict[str, str]]:
    """
    Get information about all available fetchers.

    Returns:
        List of dicts with fetcher details (type, description)

    Example:
        >>> get_available_fetchers()
        [{'type': 'rss', 'description': 'RSS/Atom feed fetcher'}, ...]
    """
    _load_fetcher_extensions()  # Ensure extensions are loaded
    fetchers = []
    for source_type in list_fetchers():
        try:
            fetcher = get_fetcher(source_type)
            fetchers.append({
                'type': source_type,
                'description': fetcher.get_description(),
            })
        except Exception:
            continue
    return fetchers


__all__ = [
    'get_fetcher',
    'fetch_content',
    'list_fetchers',
    'list_extension_fetchers',
    'is_fetcher_registered',
    'is_fetcher_extension',
    'detect_fetcher',
    'get_fetcher_entry',
    'get_available_fetchers',
    'BaseFetcher',
    'FetchedItem',
]
