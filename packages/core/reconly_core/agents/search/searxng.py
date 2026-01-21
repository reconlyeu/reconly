"""SearXNG Search provider.

Implements web search using a self-hosted SearXNG instance.
https://docs.searxng.org/
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, ClassVar

import httpx

from reconly_core.agents.search.base import (
    SearchConnectionError,
    SearchInvalidResponseError,
    SearchProvider,
    SearchProviderError,
    SearchResult,
    SearchTimeoutError,
)

logger = logging.getLogger(__name__)

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30.0


# Legacy exceptions for backwards compatibility - now inherit from base exceptions
class SearXNGSearchError(SearchProviderError):
    """Base exception for SearXNG Search errors."""


class SearXNGConnectionError(SearXNGSearchError, SearchConnectionError):
    """Raised when connection to SearXNG instance fails."""


class SearXNGInvalidResponseError(SearXNGSearchError, SearchInvalidResponseError):
    """Raised when SearXNG returns an invalid/unparseable response."""


class SearXNGTimeoutError(SearXNGSearchError, SearchTimeoutError):
    """Raised when the request times out."""


class SearXNGProvider(SearchProvider):
    """SearXNG search provider implementation.

    Searches using a self-hosted SearXNG instance. SearXNG supports multiple
    search engines (Google, Bing, DuckDuckGo, Brave, etc.) configurable on
    the SearXNG instance.

    Example:
        provider = SearXNGProvider(base_url="http://localhost:8080")
        results = await provider.search("Python async patterns", max_results=10)
    """

    name: ClassVar[str] = "searxng"
    requires_api_key: ClassVar[bool] = False

    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Initialize SearXNG provider.

        Args:
            base_url: URL of the SearXNG instance (e.g., "http://localhost:8080")
            timeout: Request timeout in seconds
        """
        if not base_url:
            raise SearXNGConnectionError("SearXNG URL is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        """Execute a search query with one retry for transient failures.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearXNGConnectionError: If connection to SearXNG fails
            SearXNGInvalidResponseError: If response cannot be parsed
            SearXNGTimeoutError: If the request times out after retries
            SearXNGSearchError: For other errors
        """
        try:
            return await self._do_search(query, max_results)
        except (SearXNGTimeoutError, SearXNGConnectionError) as e:
            logger.debug(
                "SearXNG request failed, retrying after 1s",
                extra={"query": query, "error": str(e)},
            )
            await asyncio.sleep(1.0)
            return await self._do_search(query, max_results)

    async def _do_search(self, query: str, max_results: int) -> list[SearchResult]:
        """Execute the actual search request.

        Args:
            query: The search query string
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        search_url = f"{self.base_url}/search"

        logger.debug(
            "Searching SearXNG",
            extra={
                "query": query,
                "url": self.base_url,
                "max_results": max_results,
            },
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    search_url,
                    params={
                        "q": query,
                        "format": "json",
                        "categories": "general",
                    },
                    timeout=self.timeout,
                )

                response.raise_for_status()

                try:
                    data = response.json()
                except Exception as e:
                    raise SearXNGInvalidResponseError(
                        f"Failed to parse JSON response: {e}"
                    ) from e

                results = self._parse_response(data, max_results)

                logger.debug(
                    "SearXNG search completed",
                    extra={"query": query, "result_count": len(results)},
                )

                return results

        except httpx.TimeoutException as e:
            logger.warning(
                "SearXNG search timeout",
                extra={"query": query, "url": self.base_url},
            )
            raise SearXNGTimeoutError(f"Request timed out after {self.timeout}s") from e

        except httpx.ConnectError as e:
            logger.error(
                "SearXNG connection failed",
                extra={"query": query, "url": self.base_url, "error": str(e)},
            )
            raise SearXNGConnectionError(
                f"Failed to connect to SearXNG at {self.base_url}: {e}"
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error(
                "SearXNG HTTP error",
                extra={
                    "query": query,
                    "url": self.base_url,
                    "status_code": e.response.status_code,
                },
            )
            raise SearXNGSearchError(
                f"HTTP error {e.response.status_code}: {e.response.text}"
            ) from e

        except httpx.RequestError as e:
            logger.error(
                "SearXNG request error",
                extra={"query": query, "url": self.base_url, "error": str(e)},
            )
            raise SearXNGSearchError(f"Request failed: {e}") from e

    @staticmethod
    def _parse_response(data: dict, max_results: int) -> list[SearchResult]:
        """Parse SearXNG JSON response into SearchResult objects.

        Args:
            data: Raw JSON response from SearXNG
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects

        Raises:
            SearXNGInvalidResponseError: If response structure is invalid
        """
        if not isinstance(data, dict):
            raise SearXNGInvalidResponseError(
                f"Expected dict response, got {type(data).__name__}"
            )

        results_list = data.get("results", [])

        if not isinstance(results_list, list):
            raise SearXNGInvalidResponseError(
                f"Expected results to be a list, got {type(results_list).__name__}"
            )

        results = []

        for item in results_list[:max_results]:
            if not isinstance(item, dict):
                continue

            title = item.get("title", "")
            url = item.get("url", "")

            # SearXNG uses "content" for the snippet
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

    @classmethod
    def get_config_schema(cls) -> dict[str, Any]:
        """Return configuration schema for SearXNG provider.

        Returns:
            Dict mapping setting names to their definitions
        """
        return {
            "searxng_url": {
                "type": "string",
                "label": "SearXNG URL",
                "description": "URL for SearXNG instance",
                "default": "http://localhost:8080",
                "required": True,
                "env_var": "SEARXNG_URL",
            }
        }


# Legacy function for backwards compatibility
async def searxng_search(
    query: str,
    settings: Any,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[SearchResult]:
    """Query self-hosted SearXNG instance (legacy wrapper).

    Deprecated: Use SearXNGProvider class directly for new code.

    Args:
        query: The search query string
        settings: Agent settings containing SearXNG URL and configuration
        timeout: Request timeout in seconds

    Returns:
        List of SearchResult objects
    """
    provider = SearXNGProvider(base_url=settings.searxng_url, timeout=timeout)
    return await provider.search(query, max_results=settings.max_search_results)
