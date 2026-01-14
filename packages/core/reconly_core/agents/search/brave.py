"""Brave Search API provider.

Implements web search using the Brave Search API.
https://brave.com/search/api/
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from reconly_core.agents.settings import AgentSettings

logger = logging.getLogger(__name__)

# Brave Search API endpoint
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30.0


class BraveSearchError(Exception):
    """Base exception for Brave Search errors."""


class BraveAuthError(BraveSearchError):
    """Raised when API authentication fails (401/403)."""


class BraveRateLimitError(BraveSearchError):
    """Raised when rate limit is exceeded (429)."""


class BraveTimeoutError(BraveSearchError):
    """Raised when the request times out."""


@dataclass
class SearchResult:
    """A single search result.

    Attributes:
        title: The title of the search result
        snippet: A brief description/excerpt of the content
        url: The URL of the result
    """

    title: str
    snippet: str
    url: str


async def brave_search(
    query: str,
    settings: AgentSettings,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[SearchResult]:
    """Query Brave Search API.

    Args:
        query: The search query string
        settings: Agent settings containing API key and configuration
        timeout: Request timeout in seconds

    Returns:
        List of SearchResult objects

    Raises:
        BraveAuthError: If API key is invalid or missing
        BraveRateLimitError: If rate limit is exceeded
        BraveTimeoutError: If the request times out
        BraveSearchError: For other API errors
    """
    if not settings.brave_api_key:
        raise BraveAuthError("Brave API key is required")

    logger.debug(
        "Searching Brave",
        extra={"query": query, "max_results": settings.max_search_results},
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                BRAVE_SEARCH_URL,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_api_key,
                },
                params={
                    "q": query,
                    "count": settings.max_search_results,
                },
                timeout=timeout,
            )

            # Handle specific error codes
            if response.status_code == 401:
                raise BraveAuthError("Invalid API key")
            if response.status_code == 403:
                raise BraveAuthError("API key lacks required permissions")
            if response.status_code == 429:
                raise BraveRateLimitError("Rate limit exceeded")

            response.raise_for_status()

            data = response.json()
            results = _parse_response(data)

            logger.debug(
                "Brave search completed",
                extra={"query": query, "result_count": len(results)},
            )

            return results

    except httpx.TimeoutException as e:
        logger.warning("Brave search timeout", extra={"query": query})
        raise BraveTimeoutError(f"Request timed out after {timeout}s") from e

    except httpx.HTTPStatusError as e:
        logger.error(
            "Brave search HTTP error",
            extra={"query": query, "status_code": e.response.status_code},
        )
        raise BraveSearchError(
            f"HTTP error {e.response.status_code}: {e.response.text}"
        ) from e

    except httpx.RequestError as e:
        logger.error("Brave search request error", extra={"query": query, "error": str(e)})
        raise BraveSearchError(f"Request failed: {e}") from e


def _parse_response(data: dict) -> list[SearchResult]:
    """Parse Brave Search API response into SearchResult objects.

    Args:
        data: Raw JSON response from Brave Search API

    Returns:
        List of SearchResult objects
    """
    results = []

    # Brave returns results under "web" -> "results"
    web_results = data.get("web", {}).get("results", [])

    for item in web_results:
        title = item.get("title", "")
        url = item.get("url", "")

        # Brave uses "description" for the snippet
        snippet = item.get("description", "")

        if title and url:
            results.append(
                SearchResult(
                    title=title,
                    snippet=snippet,
                    url=url,
                )
            )

    return results
