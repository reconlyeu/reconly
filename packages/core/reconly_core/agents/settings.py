"""Agent settings dataclass for runtime configuration access.

Provides a typed interface to agent-related settings with validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.services.settings_service import SettingsService


class AgentSettingsError(Exception):
    """Raised when agent settings validation fails."""


@dataclass
class AgentSettings:
    """Runtime configuration for agent-based web research.

    Attributes:
        search_provider: The search backend to use ("searxng", "duckduckgo", "tavily")
        searxng_url: URL for SearXNG instance (required if search_provider is "searxng")
        tavily_api_key: API key for Tavily (required if search_provider is "tavily")
        max_search_results: Maximum number of search results to retrieve per query
        default_max_iterations: Default maximum iterations for agent research loops
    """

    search_provider: str = "duckduckgo"
    searxng_url: str = "http://localhost:8080"
    tavily_api_key: str | None = None
    max_search_results: int = 10
    default_max_iterations: int = 5

    @classmethod
    def from_settings_service(cls, settings: SettingsService) -> AgentSettings:
        """Create AgentSettings from a SettingsService instance.

        Args:
            settings: The settings service to read from

        Returns:
            AgentSettings populated from the settings service
        """
        return cls(
            search_provider=settings.get("agent.search_provider"),
            searxng_url=settings.get("agent.searxng_url"),
            tavily_api_key=settings.get("agent.tavily_api_key"),
            max_search_results=settings.get("agent.max_search_results"),
            default_max_iterations=settings.get("agent.default_max_iterations"),
        )

    def validate(self) -> None:
        """Validate that settings are properly configured.

        Raises:
            AgentSettingsError: If required configuration is missing for the
                selected search provider
        """
        # Import here to avoid circular dependency
        from reconly_core.agents.search import SEARCH_PROVIDERS

        if self.search_provider not in SEARCH_PROVIDERS:
            available = ", ".join(sorted(SEARCH_PROVIDERS.keys()))
            raise AgentSettingsError(
                f"Invalid search_provider '{self.search_provider}'. "
                f"Available providers: {available}."
            )

        if self.search_provider == "searxng" and not self.searxng_url:
            raise AgentSettingsError(
                "SearXNG URL required when using searxng search provider. "
                "Set the SEARXNG_URL environment variable."
            )

        if self.search_provider == "tavily" and not self.tavily_api_key:
            raise AgentSettingsError(
                "Tavily API key required when using tavily search provider. "
                "Set the TAVILY_API_KEY environment variable. "
                "Get your API key at https://tavily.com/"
            )

        # DuckDuckGo requires no configuration

        if self.max_search_results < 1:
            raise AgentSettingsError(
                f"max_search_results must be at least 1, got {self.max_search_results}"
            )

        if self.default_max_iterations < 1:
            raise AgentSettingsError(
                f"default_max_iterations must be at least 1, got {self.default_max_iterations}"
            )

    def is_configured(self) -> bool:
        """Check if the settings are valid without raising an exception.

        Returns:
            True if settings are properly configured, False otherwise
        """
        try:
            self.validate()
            return True
        except AgentSettingsError:
            return False
