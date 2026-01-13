"""Search provider integration for agent-based web research.

This module provides a unified interface for web search across multiple
search providers (Brave Search API and SearXNG).

Example:
    from reconly_core.agents.settings import AgentSettings
    from reconly_core.agents.search import web_search

    settings = AgentSettings(
        search_provider="brave",
        brave_api_key="your-api-key",
        max_search_results=10,
    )

    results_markdown = await web_search("Python async patterns", settings)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import logging

from reconly_core.agents.search.brave import (
    BraveAuthError,
    BraveRateLimitError,
    BraveSearchError,
    BraveTimeoutError,
    brave_search,
)
from reconly_core.agents.search.searxng import (
    SearXNGConnectionError,
    SearXNGInvalidResponseError,
    SearXNGSearchError,
    SearXNGTimeoutError,
    searxng_search,
)

if TYPE_CHECKING:
    from reconly_core.agents.settings import AgentSettings

logger = logging.getLogger(__name__)

# Re-export provider-specific classes
__all__ = [
    # Main dispatcher
    "web_search",
    "format_search_results",
    "SearchResult",
    # Base exception
    "WebSearchError",
    # Brave exports
    "brave_search",
    "BraveSearchError",
    "BraveAuthError",
    "BraveRateLimitError",
    "BraveTimeoutError",
    # SearXNG exports
    "searxng_search",
    "SearXNGSearchError",
    "SearXNGConnectionError",
    "SearXNGInvalidResponseError",
    "SearXNGTimeoutError",
]


class WebSearchError(Exception):
    """Base exception for web search operations."""


@dataclass
class SearchResult:
    """A unified search result from any provider.

    Attributes:
        title: The title of the search result
        snippet: A brief description/excerpt of the content
        url: The URL of the result
    """

    title: str
    snippet: str
    url: str


async def web_search(query: str, settings: AgentSettings) -> str:
    """Search via configured provider and return formatted markdown.

    Routes the search request to either Brave Search or SearXNG based on
    the settings.search_provider configuration.

    Args:
        query: The search query string
        settings: Agent settings containing provider configuration

    Returns:
        Formatted markdown string with search results suitable for LLM consumption

    Raises:
        WebSearchError: If the search fails for any reason
        ValueError: If an invalid search provider is configured
    """
    logger.info(
        "Performing web search",
        extra={"query": query, "provider": settings.search_provider},
    )

    try:
        if settings.search_provider == "brave":
            provider_results = await brave_search(query, settings)
        elif settings.search_provider == "searxng":
            provider_results = await searxng_search(query, settings)
        else:
            raise ValueError(
                f"Unknown search provider: {settings.search_provider}. "
                "Must be 'brave' or 'searxng'."
            )

        # Convert provider-specific results to unified format
        results = [
            SearchResult(
                title=r.title,
                snippet=r.snippet,
                url=r.url,
            )
            for r in provider_results
        ]

        formatted = format_search_results(results)

        logger.info(
            "Web search completed",
            extra={
                "query": query,
                "provider": settings.search_provider,
                "result_count": len(results),
            },
        )

        return formatted

    except (BraveSearchError, SearXNGSearchError) as e:
        logger.error(
            "Web search failed",
            extra={
                "query": query,
                "provider": settings.search_provider,
                "error": str(e),
            },
        )
        raise WebSearchError(f"Search failed: {e}") from e


def format_search_results(results: list[SearchResult]) -> str:
    """Format search results as markdown for LLM consumption.

    Produces a clean, readable markdown format that works well
    as context for language models.

    Args:
        results: List of SearchResult objects to format

    Returns:
        Markdown-formatted string with numbered search results
    """
    if not results:
        return "No results found."

    lines = ["Search Results:", ""]

    for i, r in enumerate(results, 1):
        lines.append(f"{i}. **{r.title}**")
        lines.append(f"   URL: {r.url}")
        if r.snippet:
            lines.append(f"   {r.snippet}")
        lines.append("")

    return "\n".join(lines)
