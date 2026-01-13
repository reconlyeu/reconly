"""Fetcher implementations for different content sources."""
from reconly_core.fetchers.factory import (
    get_fetcher,
    fetch_content,
    list_fetchers,
    is_fetcher_registered,
    detect_fetcher,
    get_available_fetchers,
)
from reconly_core.fetchers.base import (
    BaseFetcher,
    FetchedItem,
    ConfigField,
    FetcherConfigSchema,
)
from reconly_core.fetchers.registry import (
    is_fetcher_extension,
    list_extension_fetchers,
    get_fetcher_entry,
)

__all__ = [
    'get_fetcher',
    'fetch_content',
    'list_fetchers',
    'is_fetcher_registered',
    'detect_fetcher',
    'get_available_fetchers',
    'BaseFetcher',
    'FetchedItem',
    'ConfigField',
    'FetcherConfigSchema',
    # Extension-related
    'is_fetcher_extension',
    'list_extension_fetchers',
    'get_fetcher_entry',
]
