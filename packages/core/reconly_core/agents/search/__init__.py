"""Search provider integration for agent-based web research.

This module provides a unified interface for web search using class-based
search providers implementing the SearchProvider ABC.

The module uses a registry pattern for providers, making it easy to add
new search providers without modifying the core dispatch logic.

Available providers:
    - searxng: Self-hosted SearXNG instance (no API key required)
    - duckduckgo: DuckDuckGo search (no API key required)
    - tavily: Tavily AI-optimized search (API key required)

Example:
    from reconly_core.agents.settings import AgentSettings
    from reconly_core.agents.search import web_search, list_providers

    # List available providers
    providers = list_providers()  # ["duckduckgo", "searxng", "tavily"]

    # Perform a search with DuckDuckGo (no config needed)
    settings = AgentSettings(
        search_provider="duckduckgo",
        max_search_results=10,
    )

    results_markdown = await web_search("Python async patterns", settings)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from reconly_core.agents.search.base import (
    SearchAuthError,
    SearchConnectionError,
    SearchInvalidResponseError,
    SearchProvider,
    SearchProviderError,
    SearchRateLimitError,
    SearchResult,
    SearchTimeoutError,
)
from reconly_core.agents.search.duckduckgo import (
    DuckDuckGoProvider,
    DuckDuckGoRateLimitError,
    DuckDuckGoSearchError,
    DuckDuckGoTimeoutError,
)
from reconly_core.agents.search.searxng import (
    SearXNGConnectionError,
    SearXNGInvalidResponseError,
    SearXNGProvider,
    SearXNGSearchError,
    SearXNGTimeoutError,
    searxng_search,
)
from reconly_core.agents.search.tavily import (
    TavilyAuthError,
    TavilyProvider,
    TavilyRateLimitError,
    TavilySearchError,
    TavilyTimeoutError,
)

if TYPE_CHECKING:
    from reconly_core.agents.settings import AgentSettings

logger = logging.getLogger(__name__)


# Registry of available search providers: name -> provider class
SEARCH_PROVIDERS: dict[str, type[SearchProvider]] = {
    "searxng": SearXNGProvider,
    "duckduckgo": DuckDuckGoProvider,
    "tavily": TavilyProvider,
}


def get_search_provider(name: str, settings: AgentSettings) -> SearchProvider:
    """Get an instantiated search provider by name.

    Args:
        name: The provider name (e.g., "searxng")
        settings: Agent settings containing provider configuration

    Returns:
        Configured SearchProvider instance

    Raises:
        ValueError: If the provider name is not found in the registry
    """
    if name not in SEARCH_PROVIDERS:
        available = ", ".join(sorted(SEARCH_PROVIDERS.keys()))
        raise ValueError(f"Unknown search provider: {name}. Available: {available}")

    # Create provider instance with appropriate configuration
    if name == "searxng":
        return SearXNGProvider(base_url=settings.searxng_url)
    elif name == "duckduckgo":
        return DuckDuckGoProvider()
    elif name == "tavily":
        return TavilyProvider(api_key=settings.tavily_api_key or "")

    # Future providers should be added with explicit configuration above
    raise ValueError(f"Provider '{name}' found in registry but has no instantiation logic")


def get_provider_class(name: str) -> type[SearchProvider]:
    """Get a search provider class by name.

    Args:
        name: The provider name (e.g., "searxng")

    Returns:
        SearchProvider class (not instantiated)

    Raises:
        ValueError: If the provider name is not found in the registry
    """
    if name not in SEARCH_PROVIDERS:
        available = ", ".join(sorted(SEARCH_PROVIDERS.keys()))
        raise ValueError(f"Unknown search provider: {name}. Available: {available}")
    return SEARCH_PROVIDERS[name]


def list_providers() -> list[str]:
    """Return sorted list of registered provider names."""
    return sorted(SEARCH_PROVIDERS.keys())


# Legacy: Use SearchProviderError for new code
class WebSearchError(SearchProviderError):
    """Base exception for web search operations (deprecated)."""


__all__ = [
    # Main dispatcher
    "web_search",
    "format_search_results",
    # Registry functions
    "get_search_provider",
    "get_provider_class",
    "list_providers",
    "SEARCH_PROVIDERS",
    # Base classes and types
    "SearchProvider",
    "SearchResult",
    # Base exceptions (new hierarchy)
    "SearchProviderError",
    "SearchTimeoutError",
    "SearchAuthError",
    "SearchConnectionError",
    "SearchRateLimitError",
    "SearchInvalidResponseError",
    # Legacy exception (backwards compatibility)
    "WebSearchError",
    # SearXNG exports
    "SearXNGProvider",
    "searxng_search",
    "SearXNGSearchError",
    "SearXNGConnectionError",
    "SearXNGInvalidResponseError",
    "SearXNGTimeoutError",
    # DuckDuckGo exports
    "DuckDuckGoProvider",
    "DuckDuckGoSearchError",
    "DuckDuckGoRateLimitError",
    "DuckDuckGoTimeoutError",
    # Tavily exports
    "TavilyProvider",
    "TavilySearchError",
    "TavilyAuthError",
    "TavilyRateLimitError",
    "TavilyTimeoutError",
]


async def web_search(query: str, settings: AgentSettings) -> str:
    """Search via configured provider and return formatted markdown.

    Args:
        query: The search query string
        settings: Agent settings containing provider configuration

    Returns:
        Formatted markdown string with search results for LLM consumption

    Raises:
        WebSearchError: If the search fails
        ValueError: If an invalid search provider is configured
    """
    provider_name = settings.search_provider

    logger.info(
        "Performing web search",
        extra={"query": query, "provider": provider_name},
    )

    provider = get_search_provider(provider_name, settings)

    try:
        results = await provider.search(query, max_results=settings.max_search_results)

        formatted = format_search_results(results)

        logger.info(
            "Web search completed",
            extra={
                "query": query,
                "provider": provider_name,
                "result_count": len(results),
            },
        )

        return formatted

    except SearchProviderError as e:
        logger.error(
            "Web search failed",
            extra={"query": query, "provider": provider_name, "error": str(e)},
        )
        raise WebSearchError(f"Search failed: {e}") from e


def format_search_results(results: list[SearchResult]) -> str:
    """Format search results as markdown for LLM consumption."""
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
