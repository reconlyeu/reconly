"""Simple research strategy using ReAct loop.

Wraps the existing ResearchAgent to implement the ResearchStrategy interface.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from reconly_core.agents.strategies.base import ResearchStrategy

if TYPE_CHECKING:
    from reconly_core.agents.schema import AgentResult
    from reconly_core.agents.settings import AgentSettings
    from reconly_core.providers.base import BaseProvider


class SimpleStrategy(ResearchStrategy):
    """Simple research strategy using ReAct loop with web search/fetch tools.

    This strategy wraps the existing ResearchAgent that implements a basic
    ReAct (Reasoning and Acting) loop for web research.

    Attributes:
        summarizer: The LLM provider to use for generating responses
    """

    def __init__(self, summarizer: "BaseProvider"):
        """Initialize the simple research strategy.

        Args:
            summarizer: LLM provider for generating responses
        """
        self.summarizer = summarizer

    async def research(
        self,
        prompt: str,
        settings: "AgentSettings",
        max_iterations: int | None = None,
    ) -> "AgentResult":
        """Execute research using ReAct loop and return structured result.

        Args:
            prompt: The research topic or question to investigate
            settings: Agent settings with search provider configuration
            max_iterations: Maximum iterations for research loop
                (defaults to settings.default_max_iterations)

        Returns:
            AgentResult with title, content, sources, and metadata
        """
        # Import here to avoid circular dependency
        from reconly_core.agents.research import ResearchAgent

        iterations = max_iterations or settings.default_max_iterations
        agent = ResearchAgent(
            summarizer=self.summarizer,
            settings=settings,
            max_iterations=iterations,
        )
        return await agent.run(prompt)

    def estimate_duration_seconds(self) -> int:
        """Estimated time for simple research completion.

        Simple strategy typically completes in 30-60 seconds depending
        on the number of iterations and search/fetch operations.

        Returns:
            Estimated duration in seconds
        """
        return 45  # Conservative estimate for simple ReAct loop

    def estimate_cost_usd(self, model: str) -> float:
        """Estimated cost for simple research completion.

        Returns a rough estimate based on typical token usage. Actual costs
        vary by model and usage patterns - this is for UI display only.

        Args:
            model: The LLM model identifier (used for future refinement)

        Returns:
            Estimated cost in USD (conservative mid-tier estimate)
        """
        # Simple strategy: ~5 iterations, ~2k input + ~500 output tokens each
        # Using conservative mid-tier pricing ($0.01/1k input, $0.03/1k output)
        # Total: (10k * 0.01 + 2.5k * 0.03) / 1000 = 0.175
        return 0.18
