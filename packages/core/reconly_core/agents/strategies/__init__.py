"""Research strategy implementations.

This module provides different research execution strategies:
- simple: ReAct loop with web search/fetch (default, no extra dependencies)
- comprehensive: GPT Researcher comprehensive mode (requires gpt-researcher)
- deep: GPT Researcher deep research mode (requires gpt-researcher)

Use get_strategy() to obtain a strategy instance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from reconly_core.agents.strategies.base import ResearchStrategy

if TYPE_CHECKING:
    from reconly_core.providers.base import BaseProvider

__all__ = [
    "AVAILABLE_STRATEGIES",
    "ResearchStrategy",
    "get_strategy",
]


AVAILABLE_STRATEGIES = ("simple", "comprehensive", "deep")


def get_strategy(strategy_name: str, **kwargs) -> ResearchStrategy:
    """Factory function to get a research strategy by name.

    Args:
        strategy_name: The strategy to use:
            - "simple": ReAct loop with web search/fetch (default)
            - "comprehensive": GPT Researcher comprehensive research
            - "deep": GPT Researcher deep research with subtopics
        **kwargs: Strategy-specific arguments:
            - summarizer: LLM provider instance (required for simple, optional for others)

    Returns:
        ResearchStrategy instance

    Raises:
        ValueError: If strategy_name is unknown or required argument is missing
        ImportError: If GPT Researcher is not installed for comprehensive/deep strategies
    """
    if strategy_name == "simple":
        from reconly_core.agents.strategies.simple import SimpleStrategy

        summarizer = kwargs.get("summarizer")
        if summarizer is None:
            raise ValueError("SimpleStrategy requires 'summarizer' argument")
        return SimpleStrategy(summarizer=summarizer)

    if strategy_name in ("comprehensive", "deep"):
        # Lazy import to avoid loading GPT Researcher (and LangChain) unnecessarily
        try:
            from reconly_core.agents.strategies.gpt_researcher import (
                GPTResearcherStrategy,
            )
        except ImportError as e:
            raise ImportError(
                f"GPT Researcher strategy requires the 'research' extra. "
                f"Install with: pip install reconly-core[research]\n"
                f"Original error: {e}"
            ) from e

        return GPTResearcherStrategy(deep_mode=(strategy_name == "deep"), **kwargs)

    raise ValueError(
        f"Unknown strategy: {strategy_name}. "
        f"Available strategies: {', '.join(AVAILABLE_STRATEGIES)}"
    )
