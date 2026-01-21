"""Agent source components for autonomous web research.

This module provides:
- AgentSettings: Configuration for agent search providers
- AgentResult: Structured output from research operations
- ResearchAgent: ReAct loop agent for web research
- web_search: Search dispatcher for search providers (SearXNG, etc.)
- web_fetch: URL content fetcher
- get_agent_capabilities: Discover available research strategies
"""
from reconly_core.agents.schema import AgentResult
from reconly_core.agents.settings import AgentSettings, AgentSettingsError
from reconly_core.agents.research import ResearchAgent, AGENT_SYSTEM_PROMPT
from reconly_core.agents.search import (
    web_search,
    format_search_results,
    SearchResult,
    WebSearchError,
)
from reconly_core.agents.fetch import (
    web_fetch,
    format_fetch_result,
    FetchResult,
    WebFetchError,
    WebFetchTimeoutError,
    WebFetchHTTPError,
)
from reconly_core.agents.capabilities import (
    get_agent_capabilities,
    AgentCapabilities,
    StrategyInfo,
    is_gpt_researcher_installed,
    get_available_search_providers,
)

__all__ = [
    # Schema
    "AgentResult",
    # Settings
    "AgentSettings",
    "AgentSettingsError",
    # Research Agent
    "ResearchAgent",
    "AGENT_SYSTEM_PROMPT",
    # Search
    "web_search",
    "format_search_results",
    "SearchResult",
    "WebSearchError",
    # Fetch
    "web_fetch",
    "format_fetch_result",
    "FetchResult",
    "WebFetchError",
    "WebFetchTimeoutError",
    "WebFetchHTTPError",
    # Capabilities
    "get_agent_capabilities",
    "AgentCapabilities",
    "StrategyInfo",
    "is_gpt_researcher_installed",
    "get_available_search_providers",
]
