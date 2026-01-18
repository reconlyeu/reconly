"""Provider capabilities dataclass for runtime feature discovery.

Edition Notes:
    - OSS edition: cost_per_1k_input and cost_per_1k_output are always 0.0
    - Enterprise edition: Providers override with actual pricing
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelInfo:
    """Information about an available model.

    Attributes:
        id: Model identifier (e.g., "claude-sonnet-4-20250514")
        name: Display name (e.g., "Claude Sonnet 4")
        provider: Provider name (e.g., "anthropic", "openai")
        is_default: Whether this is the provider's default model
        deprecated: Whether model is deprecated
    """

    id: str
    name: str
    provider: str
    is_default: bool = False
    deprecated: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "is_default": self.is_default,
            "deprecated": self.deprecated,
        }


@dataclass
class ProviderCapabilities:
    """
    Describes the capabilities of a provider.

    Attributes:
        supports_streaming: Whether provider supports streaming responses
        supports_async: Whether provider supports async/await operations
        requires_api_key: Whether provider requires an API key
        is_local: Whether provider runs locally (not cloud-based)
        max_context_tokens: Maximum context window size in tokens (None if unlimited/unknown)
        cost_per_1k_input: Cost per 1,000 input tokens in USD (0.0 in OSS edition)
        cost_per_1k_output: Cost per 1,000 output tokens in USD (0.0 in OSS edition)
    """

    supports_streaming: bool = False
    supports_async: bool = False
    requires_api_key: bool = True
    is_local: bool = False
    max_context_tokens: Optional[int] = None
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None

    def is_free(self) -> bool:
        """
        Check if provider is free (zero cost).

        Returns:
            True if both cost_per_1k_input and cost_per_1k_output are 0.0 or None
        """
        return (
            (self.cost_per_1k_input is None or self.cost_per_1k_input == 0.0) and
            (self.cost_per_1k_output is None or self.cost_per_1k_output == 0.0)
        )

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for given token counts.

        Note: In OSS edition, this always returns 0.0 since cost fields are stubbed.
        Enterprise edition provides actual pricing.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD (0.0 in OSS edition)
        """
        input_cost = 0.0
        output_cost = 0.0

        if self.cost_per_1k_input is not None:
            input_cost = (input_tokens / 1000.0) * self.cost_per_1k_input

        if self.cost_per_1k_output is not None:
            output_cost = (output_tokens / 1000.0) * self.cost_per_1k_output

        return input_cost + output_cost
