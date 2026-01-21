"""DuckDuckGo Search provider.

Implements web search using the DuckDuckGo search engine via the
duckduckgo-search library. This provider requires no API key and
works out of the box.

https://github.com/deedy5/duckduckgo_search
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar

from reconly_core.agents.search.base import (
    SearchProvider,
    SearchProviderError,
    SearchRateLimitError,
    SearchResult,
    SearchTimeoutError,
)

logger = logging.getLogger(__name__)

# Default timeout for search operations (seconds)
DEFAULT_TIMEOUT = 30.0

# Exponential backoff settings for rate limiting
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds
BACKOFF_MULTIPLIER = 2.0


class DuckDuckGoSearchError(SearchProviderError):
    """Base exception for DuckDuckGo search errors."""


class DuckDuckGoRateLimitError(DuckDuckGoSearchError, SearchRateLimitError):
    """Raised when DuckDuckGo rate limit is exceeded."""


class DuckDuckGoTimeoutError(DuckDuckGoSearchError, SearchTimeoutError):
    """Raised when a DuckDuckGo search request times out."""


class DuckDuckGoProvider(SearchProvider):
    """DuckDuckGo search provider implementation.

    Uses the duckduckgo-search library for web searches. This provider
    requires no API key and works without any configuration.

    The library uses synchronous HTTP requests, so we run searches in
    a thread pool executor to avoid blocking the event loop.

    Example:
        provider = DuckDuckGoProvider()
        results = await provider.search("Python async patterns", max_results=10)

    Note:
        DuckDuckGo may rate limit requests. This provider implements
        exponential backoff to handle rate limiting gracefully.
    """

    name: ClassVar[str] = "duckduckgo"
    requires_api_key: ClassVar[bool] = False

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize DuckDuckGo provider.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute a search query with exponential backoff for rate limiting.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            DuckDuckGoRateLimitError: If rate limit is exceeded after all retries
            DuckDuckGoTimeoutError: If the request times out
            DuckDuckGoSearchError: For other search errors
        """
        logger.debug(
            "Searching DuckDuckGo",
            extra={"query": query, "max_results": max_results},
        )

        loop = asyncio.get_running_loop()
        backoff = INITIAL_BACKOFF
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, self._search_sync, query, max_results
                    ),
                    timeout=self.timeout,
                )

                logger.debug(
                    "DuckDuckGo search completed",
                    extra={"query": query, "result_count": len(results)},
                )

                return results

            except asyncio.TimeoutError as e:
                logger.warning(
                    "DuckDuckGo search timeout",
                    extra={"query": query, "attempt": attempt + 1},
                )
                raise DuckDuckGoTimeoutError(
                    f"Search timed out after {self.timeout}s"
                ) from e

            except DuckDuckGoRateLimitError as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.info(
                        "DuckDuckGo rate limited, backing off",
                        extra={
                            "query": query,
                            "attempt": attempt + 1,
                            "backoff_seconds": backoff,
                        },
                    )
                    await asyncio.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER
                else:
                    logger.warning(
                        "DuckDuckGo rate limit exceeded after all retries",
                        extra={"query": query, "attempts": MAX_RETRIES},
                    )

        # If we exhausted all retries, raise the last error
        # Note: last_error is always set when we exit the loop via rate limiting
        raise last_error  # type: ignore[misc]

    def _search_sync(self, query: str, max_results: int) -> list[SearchResult]:
        """Execute synchronous search using duckduckgo-search library.

        This method runs in a thread pool executor.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            DuckDuckGoRateLimitError: If rate limit is exceeded
            DuckDuckGoSearchError: For other search errors
        """
        try:
            from duckduckgo_search import DDGS
            from duckduckgo_search.exceptions import RatelimitException
        except ImportError as e:
            raise DuckDuckGoSearchError(
                "duckduckgo-search not installed. "
                "Install with: pip install duckduckgo-search"
            ) from e

        try:
            with DDGS() as ddgs:
                raw_results = ddgs.text(query, max_results=max_results)

                if raw_results is None:
                    return []

                results = []
                for item in raw_results:
                    if not isinstance(item, dict):
                        continue

                    title = item.get("title", "")
                    url = item.get("href", "")
                    snippet = item.get("body", "")

                    if title and url:
                        results.append(
                            SearchResult(
                                title=title,
                                snippet=snippet,
                                url=url,
                            )
                        )

                return results

        except RatelimitException as e:
            raise DuckDuckGoRateLimitError(
                "DuckDuckGo rate limit exceeded. Please wait before retrying."
            ) from e

        except Exception as e:
            error_str = str(e).lower()
            if "ratelimit" in error_str or "rate limit" in error_str:
                raise DuckDuckGoRateLimitError(
                    "DuckDuckGo rate limit exceeded"
                ) from e
            raise DuckDuckGoSearchError(f"DuckDuckGo search failed: {e}") from e

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Return configuration schema for DuckDuckGo provider.

        DuckDuckGo requires no configuration.

        Returns:
            Empty dict (no configuration needed)
        """
        return {}
