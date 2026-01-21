"""Base classes and interfaces for search providers.

This module defines the SearchProvider abstract base class that all search
providers must implement, along with common data structures and exceptions.

Example:
    from reconly_core.agents.search.base import SearchProvider, SearchResult

    class MySearchProvider(SearchProvider):
        name = "my_search"
        requires_api_key = True

        async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
            # Implementation here
            ...
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class SearchResult:
    """A unified search result from any provider.

    This is the single source of truth for search results across all providers.
    All provider implementations should return lists of this dataclass.

    Attributes:
        title: The title of the search result
        snippet: A brief description/excerpt of the content
        url: The URL of the result
    """

    title: str
    snippet: str
    url: str


class SearchProviderError(Exception):
    """Base exception for all search provider errors.

    All provider-specific exceptions should inherit from this class to enable
    unified error handling in the search dispatcher.
    """


class SearchTimeoutError(SearchProviderError):
    """Raised when a search request times out (transient, may succeed on retry)."""


class SearchAuthError(SearchProviderError):
    """Raised when authentication/authorization fails (missing/invalid API key)."""


class SearchConnectionError(SearchProviderError):
    """Raised when connection to the search service fails."""


class SearchRateLimitError(SearchProviderError):
    """Raised when rate limit is exceeded (transient, may succeed after waiting)."""


class SearchInvalidResponseError(SearchProviderError):
    """Raised when the search service returns an unparseable response."""


class SearchProvider(ABC):
    """Abstract base class for search providers.

    All search provider implementations must inherit from this class and
    implement the required abstract methods.

    Attributes:
        name: Unique identifier for this provider (e.g., "tavily", "duckduckgo")
        requires_api_key: Whether this provider requires an API key to function
    """

    name: ClassVar[str]
    requires_api_key: ClassVar[bool]

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute a search query and return results.

        Args:
            query: The search query string
            max_results: Maximum number of results to return (default: 10)

        Returns:
            List of SearchResult objects

        Raises:
            SearchProviderError: Or any of its subclasses (SearchTimeoutError,
                SearchAuthError, SearchConnectionError, SearchRateLimitError,
                SearchInvalidResponseError)
        """
        ...

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Return settings this provider needs for auto-registration.

        Override this to declare configuration requirements. Returns a dict
        mapping setting names to SettingDef objects.
        """
        return {}
