"""SearXNG Search provider.

Implements web search using a self-hosted SearXNG instance.
https://docs.searxng.org/
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from reconly_core.agents.settings import AgentSettings

logger = logging.getLogger(__name__)

# Default timeout for API requests (seconds)
DEFAULT_TIMEOUT = 30.0


class SearXNGSearchError(Exception):
    """Base exception for SearXNG Search errors."""


class SearXNGConnectionError(SearXNGSearchError):
    """Raised when connection to SearXNG instance fails."""


class SearXNGInvalidResponseError(SearXNGSearchError):
    """Raised when SearXNG returns an invalid/unparseable response."""


class SearXNGTimeoutError(SearXNGSearchError):
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


async def searxng_search(
    query: str,
    settings: AgentSettings,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[SearchResult]:
    """Query self-hosted SearXNG instance.

    Args:
        query: The search query string
        settings: Agent settings containing SearXNG URL and configuration
        timeout: Request timeout in seconds

    Returns:
        List of SearchResult objects

    Raises:
        SearXNGConnectionError: If connection to SearXNG fails
        SearXNGInvalidResponseError: If response cannot be parsed
        SearXNGTimeoutError: If the request times out
        SearXNGSearchError: For other errors
    """
    if not settings.searxng_url:
        raise SearXNGConnectionError("SearXNG URL is required")

    # Normalize URL (remove trailing slash)
    base_url = settings.searxng_url.rstrip("/")
    search_url = f"{base_url}/search"

    logger.debug(
        "Searching SearXNG",
        extra={
            "query": query,
            "url": base_url,
            "max_results": settings.max_search_results,
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
                timeout=timeout,
            )

            response.raise_for_status()

            try:
                data = response.json()
            except Exception as e:
                raise SearXNGInvalidResponseError(
                    f"Failed to parse JSON response: {e}"
                ) from e

            results = _parse_response(data, settings.max_search_results)

            logger.debug(
                "SearXNG search completed",
                extra={"query": query, "result_count": len(results)},
            )

            return results

    except httpx.TimeoutException as e:
        logger.warning("SearXNG search timeout", extra={"query": query, "url": base_url})
        raise SearXNGTimeoutError(f"Request timed out after {timeout}s") from e

    except httpx.ConnectError as e:
        logger.error(
            "SearXNG connection failed",
            extra={"query": query, "url": base_url, "error": str(e)},
        )
        raise SearXNGConnectionError(
            f"Failed to connect to SearXNG at {base_url}: {e}"
        ) from e

    except httpx.HTTPStatusError as e:
        logger.error(
            "SearXNG HTTP error",
            extra={"query": query, "url": base_url, "status_code": e.response.status_code},
        )
        raise SearXNGSearchError(
            f"HTTP error {e.response.status_code}: {e.response.text}"
        ) from e

    except httpx.RequestError as e:
        logger.error(
            "SearXNG request error",
            extra={"query": query, "url": base_url, "error": str(e)},
        )
        raise SearXNGSearchError(f"Request failed: {e}") from e


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
