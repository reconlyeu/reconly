"""Tavily Search provider.

Implements web search using the Tavily AI-optimized search API.
Tavily provides search results specifically designed for LLM consumption.

https://tavily.com/

Note:
    This provider requires the optional `tavily-python` package.
    Install with: pip install tavily-python
    Or install reconly-core with: pip install reconly-core[research]
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar

from reconly_core.agents.search.base import (
    SearchAuthError,
    SearchProvider,
    SearchProviderError,
    SearchRateLimitError,
    SearchResult,
    SearchTimeoutError,
)

logger = logging.getLogger(__name__)

# Default timeout for search operations (seconds)
DEFAULT_TIMEOUT = 30.0


class TavilySearchError(SearchProviderError):
    """Base exception for Tavily search errors."""


class TavilyAuthError(TavilySearchError, SearchAuthError):
    """Raised when Tavily authentication fails (invalid or missing API key)."""


class TavilyRateLimitError(TavilySearchError, SearchRateLimitError):
    """Raised when Tavily rate limit is exceeded."""


class TavilyTimeoutError(TavilySearchError, SearchTimeoutError):
    """Raised when a Tavily search request times out."""


class TavilyProvider(SearchProvider):
    """Tavily AI-optimized search provider implementation.

    Uses the Tavily API for web searches. Tavily is designed specifically
    for LLM applications and provides high-quality search results with
    relevant content snippets.

    The library uses synchronous HTTP requests, so we run searches in
    a thread pool executor to avoid blocking the event loop.

    Example:
        provider = TavilyProvider(api_key="tvly-...")
        results = await provider.search("Python async patterns", max_results=10)

    Note:
        Tavily requires an API key. Free tier includes 1000 searches/month.
        Get your API key at https://tavily.com/
    """

    name: ClassVar[str] = "tavily"
    requires_api_key: ClassVar[bool] = True

    def __init__(self, api_key: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize Tavily provider.

        Args:
            api_key: Tavily API key (required)
            timeout: Request timeout in seconds

        Raises:
            TavilyAuthError: If api_key is empty or None
        """
        if not api_key:
            raise TavilyAuthError(
                "Tavily API key is required. "
                "Get your API key at https://tavily.com/"
            )
        self._api_key = api_key
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute a search query using the Tavily API.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            TavilyAuthError: If authentication fails (invalid API key)
            TavilyRateLimitError: If rate limit is exceeded
            TavilyTimeoutError: If the request times out
            TavilySearchError: For other search errors
        """
        logger.debug(
            "Searching Tavily",
            extra={"query": query, "max_results": max_results},
        )

        loop = asyncio.get_running_loop()

        try:
            results = await asyncio.wait_for(
                loop.run_in_executor(None, self._search_sync, query, max_results),
                timeout=self.timeout,
            )

            logger.debug(
                "Tavily search completed",
                extra={"query": query, "result_count": len(results)},
            )

            return results

        except asyncio.TimeoutError as e:
            logger.warning(
                "Tavily search timeout",
                extra={"query": query, "timeout": self.timeout},
            )
            raise TavilyTimeoutError(
                f"Search timed out after {self.timeout}s"
            ) from e

    def _search_sync(self, query: str, max_results: int) -> list[SearchResult]:
        """Execute synchronous search using tavily-python library.

        This method runs in a thread pool executor.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            TavilyAuthError: If authentication fails
            TavilyRateLimitError: If rate limit is exceeded
            TavilySearchError: For other search errors
        """
        try:
            from tavily import TavilyClient
        except ImportError as e:
            raise TavilySearchError(
                "tavily-python not installed. "
                "Install with: pip install tavily-python "
                "or pip install reconly-core[research]"
            ) from e

        try:
            client = TavilyClient(api_key=self._api_key)
            response = client.search(query=query, max_results=max_results)

            raw_results = response.get("results", [])

            results = []
            for item in raw_results:
                if not isinstance(item, dict):
                    continue

                title = item.get("title", "")
                url = item.get("url", "")
                # Tavily uses "content" for the snippet
                snippet = item.get("content", "")

                if title and url:
                    results.append(
                        SearchResult(
                            title=title,
                            snippet=snippet,
                            url=url,
                        )
                    )

            return results

        except Exception as e:
            error_str = str(e).lower()

            # Check for authentication errors
            if (
                "401" in str(e)
                or "unauthorized" in error_str
                or "invalid api key" in error_str
                or "api key" in error_str and "invalid" in error_str
            ):
                logger.error(
                    "Tavily authentication failed",
                    extra={"error": str(e)},
                )
                raise TavilyAuthError(
                    "Invalid Tavily API key. Check your API key at https://tavily.com/"
                ) from e

            # Check for rate limit errors
            if (
                "429" in str(e)
                or "rate limit" in error_str
                or "too many requests" in error_str
                or "quota" in error_str
            ):
                logger.warning(
                    "Tavily rate limit exceeded",
                    extra={"error": str(e)},
                )
                raise TavilyRateLimitError(
                    "Tavily rate limit exceeded. Free tier: 1000 searches/month."
                ) from e

            # Generic error
            logger.error(
                "Tavily search failed",
                extra={"query": query, "error": str(e)},
            )
            raise TavilySearchError(f"Tavily search failed: {e}") from e

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Return configuration schema for Tavily provider.

        Returns:
            Dict mapping setting names to their definitions
        """
        return {
            "tavily_api_key": {
                "type": "string",
                "label": "Tavily API Key",
                "description": (
                    "API key from tavily.com (free tier: 1000 searches/month)"
                ),
                "required": True,
                "env_var": "TAVILY_API_KEY",
                "secret": True,
                "editable": False,
            }
        }
