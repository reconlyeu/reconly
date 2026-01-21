"""Agent research capabilities discovery.

This module provides utilities for discovering what research capabilities
are available in the current environment, including whether GPT Researcher
is installed and which search providers are configured.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.agents.settings import AgentSettings


@dataclass
class StrategyInfo:
    """Information about a research strategy."""

    available: bool
    description: str
    estimated_duration_seconds: int | None = None
    requires_api_key: bool = False


@dataclass
class AgentCapabilities:
    """Describes the available agent research capabilities.

    Attributes:
        strategies: Dict mapping strategy name to its availability info
        gpt_researcher_installed: Whether gpt-researcher package is available
        search_providers: List of available search provider names
        configured_search_provider: Currently configured search provider (or None)
    """

    strategies: dict[str, StrategyInfo] = field(default_factory=dict)
    gpt_researcher_installed: bool = False
    search_providers: list[str] = field(default_factory=list)
    configured_search_provider: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "strategies": {
                name: {
                    "available": info.available,
                    "description": info.description,
                    "estimated_duration_seconds": info.estimated_duration_seconds,
                    "requires_api_key": info.requires_api_key,
                }
                for name, info in self.strategies.items()
            },
            "gpt_researcher_installed": self.gpt_researcher_installed,
            "search_providers": self.search_providers,
            "configured_search_provider": self.configured_search_provider,
        }


def is_gpt_researcher_installed() -> bool:
    """Check if gpt-researcher package is installed.

    Returns:
        True if gpt-researcher is importable, False otherwise.
    """
    try:
        import gpt_researcher  # noqa: F401

        return True
    except ImportError:
        return False


def get_available_search_providers() -> list[str]:
    """Get list of available search provider names.

    Returns:
        Sorted list of search provider names (e.g., ["duckduckgo", "searxng", "tavily"])
    """
    from reconly_core.agents.search import list_providers

    return list_providers()


def get_agent_capabilities(settings: "AgentSettings | None" = None) -> AgentCapabilities:
    """Discover available agent research capabilities.

    Args:
        settings: Optional AgentSettings to check configuration. If not provided,
            only checks installation status without configuration validation.

    Returns:
        AgentCapabilities describing what's available in the current environment.
    """
    gpt_researcher_installed = is_gpt_researcher_installed()
    search_providers = get_available_search_providers()

    # Determine configured search provider
    configured_provider = None
    if settings:
        configured_provider = settings.search_provider

    # Build strategy info
    strategies = {
        "simple": StrategyInfo(
            available=True,  # Always available - uses basic ReAct loop
            description="Quick research using web search and fetch (~30s)",
            estimated_duration_seconds=30,
            requires_api_key=False,  # Uses existing LLM provider
        ),
        "comprehensive": StrategyInfo(
            available=gpt_researcher_installed,
            description="Comprehensive research with multiple sources (~3min)",
            estimated_duration_seconds=180,
            requires_api_key=False,  # Uses configured LLM + search provider
        ),
        "deep": StrategyInfo(
            available=gpt_researcher_installed,
            description="Deep research with subtopic exploration (~5min)",
            estimated_duration_seconds=300,
            requires_api_key=False,
        ),
    }

    return AgentCapabilities(
        strategies=strategies,
        gpt_researcher_installed=gpt_researcher_installed,
        search_providers=search_providers,
        configured_search_provider=configured_provider,
    )
