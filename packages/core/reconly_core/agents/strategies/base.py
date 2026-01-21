"""Base class for research execution strategies.

Defines the interface that all research strategies must implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.agents.schema import AgentResult
    from reconly_core.agents.settings import AgentSettings


class ResearchStrategy(ABC):
    """Base class for research execution strategies.

    All research strategies (simple ReAct, GPT Researcher comprehensive,
    GPT Researcher deep) must implement this interface.
    """

    @abstractmethod
    async def research(
        self,
        prompt: str,
        settings: "AgentSettings",
        max_iterations: int | None = None,
    ) -> "AgentResult":
        """Execute research and return structured result.

        Args:
            prompt: The research topic or question to investigate
            settings: Agent settings with search provider configuration
            max_iterations: Maximum iterations for research loop (strategy-dependent)

        Returns:
            AgentResult with title, content, sources, and metadata
        """
        ...

    @abstractmethod
    def estimate_duration_seconds(self) -> int:
        """Estimated time for research completion.

        Returns:
            Estimated duration in seconds
        """
        ...

    @abstractmethod
    def estimate_cost_usd(self, model: str) -> float:
        """Estimated cost for research completion.

        Args:
            model: The LLM model identifier being used

        Returns:
            Estimated cost in USD
        """
        ...
