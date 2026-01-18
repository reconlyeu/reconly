"""Tests for provider capabilities."""
import pytest
from reconly_core.providers.capabilities import ProviderCapabilities


class TestProviderCapabilities:
    """Test cases for ProviderCapabilities dataclass."""

    def test_default_capabilities(self):
        """Test default capability values."""
        caps = ProviderCapabilities()

        assert caps.supports_streaming is False
        assert caps.supports_async is False
        assert caps.requires_api_key is True
        assert caps.is_local is False
        assert caps.max_context_tokens is None
        assert caps.cost_per_1k_input is None
        assert caps.cost_per_1k_output is None

    def test_custom_capabilities(self):
        """Test setting custom capability values."""
        caps = ProviderCapabilities(
            supports_streaming=True,
            supports_async=True,
            requires_api_key=False,
            is_local=True,
            max_context_tokens=128000,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0
        )

        assert caps.supports_streaming is True
        assert caps.supports_async is True
        assert caps.requires_api_key is False
        assert caps.is_local is True
        assert caps.max_context_tokens == 128000
        assert caps.cost_per_1k_input == 0.0
        assert caps.cost_per_1k_output == 0.0

    def test_is_free_with_zero_costs(self):
        """Test is_free() returns True when costs are 0.0."""
        caps = ProviderCapabilities(
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0
        )

        assert caps.is_free() is True

    def test_is_free_with_none_costs(self):
        """Test is_free() returns True when costs are None."""
        caps = ProviderCapabilities(
            cost_per_1k_input=None,
            cost_per_1k_output=None
        )

        assert caps.is_free() is True

    def test_is_free_mixed_none_and_zero(self):
        """Test is_free() returns True when costs are mix of None and 0.0."""
        caps = ProviderCapabilities(
            cost_per_1k_input=None,
            cost_per_1k_output=0.0
        )

        assert caps.is_free() is True

        caps2 = ProviderCapabilities(
            cost_per_1k_input=0.0,
            cost_per_1k_output=None
        )

        assert caps2.is_free() is True

    def test_is_free_with_nonzero_input_cost(self):
        """Test is_free() returns False when input cost is > 0."""
        caps = ProviderCapabilities(
            cost_per_1k_input=0.5,
            cost_per_1k_output=0.0
        )

        assert caps.is_free() is False

    def test_is_free_with_nonzero_output_cost(self):
        """Test is_free() returns False when output cost is > 0."""
        caps = ProviderCapabilities(
            cost_per_1k_input=0.0,
            cost_per_1k_output=1.5
        )

        assert caps.is_free() is False

    def test_is_free_with_both_nonzero(self):
        """Test is_free() returns False when both costs are > 0."""
        caps = ProviderCapabilities(
            cost_per_1k_input=3.0,
            cost_per_1k_output=15.0
        )

        assert caps.is_free() is False

    def test_estimated_cost_zero_when_costs_none(self):
        """Test estimated_cost returns 0.0 when costs are None."""
        caps = ProviderCapabilities(
            cost_per_1k_input=None,
            cost_per_1k_output=None
        )

        cost = caps.estimated_cost(input_tokens=1000, output_tokens=500)
        assert cost == 0.0

    def test_estimated_cost_calculation(self):
        """Test estimated_cost calculation with known values."""
        # GPT-4-turbo pricing
        caps = ProviderCapabilities(
            cost_per_1k_input=10.0,  # $10 per 1M tokens = $0.01 per 1K tokens
            cost_per_1k_output=30.0  # $30 per 1M tokens = $0.03 per 1K tokens
        )

        # 1000 input tokens, 500 output tokens
        cost = caps.estimated_cost(input_tokens=1000, output_tokens=500)

        # Expected: (1000/1000 * 10.0) + (500/1000 * 30.0) = 10.0 + 15.0 = 25.0
        assert cost == 25.0

    def test_estimated_cost_partial_pricing(self):
        """Test estimated_cost when only input cost is set."""
        caps = ProviderCapabilities(
            cost_per_1k_input=0.5,
            cost_per_1k_output=None
        )

        cost = caps.estimated_cost(input_tokens=2000, output_tokens=500)

        # Expected: (2000/1000 * 0.5) + 0 = 1.0
        assert cost == 1.0

    def test_estimated_cost_fractional_tokens(self):
        """Test estimated_cost with fractional token counts."""
        caps = ProviderCapabilities(
            cost_per_1k_input=3.0,
            cost_per_1k_output=15.0
        )

        # 500 input tokens, 100 output tokens
        cost = caps.estimated_cost(input_tokens=500, output_tokens=100)

        # Expected: (500/1000 * 3.0) + (100/1000 * 15.0) = 1.5 + 1.5 = 3.0
        assert cost == 3.0

    def test_estimated_cost_large_numbers(self):
        """Test estimated_cost with large token counts."""
        caps = ProviderCapabilities(
            cost_per_1k_input=0.001,
            cost_per_1k_output=0.002
        )

        # 1 million input tokens, 500k output tokens
        cost = caps.estimated_cost(input_tokens=1_000_000, output_tokens=500_000)

        # Expected: (1_000_000/1000 * 0.001) + (500_000/1000 * 0.002) = 1.0 + 1.0 = 2.0
        assert cost == 2.0

    def test_anthropic_claude_capabilities(self):
        """Test realistic Anthropic Claude capabilities."""
        caps = ProviderCapabilities(
            supports_streaming=False,
            supports_async=False,
            requires_api_key=True,
            is_local=False,
            max_context_tokens=200_000,
            cost_per_1k_input=3.0,
            cost_per_1k_output=15.0
        )

        assert caps.is_free() is False
        assert caps.is_local is False
        assert caps.requires_api_key is True

    def test_ollama_capabilities(self):
        """Test realistic Ollama (local) capabilities."""
        caps = ProviderCapabilities(
            supports_streaming=False,
            supports_async=False,
            requires_api_key=False,
            is_local=True,
            max_context_tokens=None,  # Depends on model
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0
        )

        assert caps.is_free() is True
        assert caps.is_local is True
        assert caps.requires_api_key is False
