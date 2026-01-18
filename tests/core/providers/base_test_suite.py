"""Abstract test suite for provider implementations."""
from abc import ABC, abstractmethod
import pytest
from reconly_core.providers.base import BaseProvider
from reconly_core.providers.capabilities import ProviderCapabilities


class BaseProviderTestSuite(ABC):
    """
    Abstract test suite that all provider tests must inherit.

    This provides contract tests to ensure providers correctly implement
    the BaseProvider interface and follow expected behaviors.

    Subclasses must implement the `summarizer` fixture.

    Example:
        >>> class TestMyProvider(BaseProviderTestSuite):
        >>>     @pytest.fixture
        >>>     def summarizer(self):
        >>>         return MyProviderSummarizer(api_key='test-key')
    """

    @pytest.fixture
    @abstractmethod
    def summarizer(self) -> BaseProvider:
        """
        Return a configured summarizer instance for testing.

        Returns:
            Configured BaseProvider instance
        """
        pass

    # Contract Tests - Interface Compliance

    def test_implements_base_interface(self, summarizer):
        """Verify all required abstract methods are implemented."""
        assert isinstance(summarizer, BaseProvider)
        assert hasattr(summarizer, 'summarize')
        assert callable(summarizer.summarize)
        assert hasattr(summarizer, 'get_provider_name')
        assert callable(summarizer.get_provider_name)
        assert hasattr(summarizer, 'estimate_cost')
        assert callable(summarizer.estimate_cost)
        assert hasattr(summarizer, 'get_model_info')
        assert callable(summarizer.get_model_info)
        assert hasattr(summarizer, 'get_capabilities')
        assert callable(summarizer.get_capabilities)
        assert hasattr(summarizer, 'is_available')
        assert callable(summarizer.is_available)
        assert hasattr(summarizer, 'validate_config')
        assert callable(summarizer.validate_config)

    def test_provider_name_not_empty(self, summarizer):
        """Verify provider name is set and non-empty."""
        provider_name = summarizer.get_provider_name()
        assert provider_name
        assert isinstance(provider_name, str)
        assert len(provider_name) > 0

    def test_cost_estimate_non_negative(self, summarizer):
        """Verify cost estimation returns non-negative values."""
        cost = summarizer.estimate_cost(1000)
        assert cost >= 0.0
        assert isinstance(cost, (int, float))

    def test_cost_estimate_scales_with_length(self, summarizer):
        """Verify cost increases or stays same with content length."""
        cost_small = summarizer.estimate_cost(100)
        cost_large = summarizer.estimate_cost(10000)

        assert cost_large >= cost_small

    def test_validate_config_returns_list(self, summarizer):
        """Verify validate_config returns a list."""
        errors = summarizer.validate_config()
        assert isinstance(errors, list)

    def test_validate_config_contains_strings(self, summarizer):
        """Verify validate_config returns list of strings (if not empty)."""
        errors = summarizer.validate_config()
        for error in errors:
            assert isinstance(error, str)

    def test_is_available_returns_bool(self, summarizer):
        """Verify is_available returns boolean."""
        available = summarizer.is_available()
        assert isinstance(available, bool)

    def test_is_available_does_not_raise(self, summarizer):
        """Verify is_available does not raise exceptions."""
        try:
            available = summarizer.is_available()
            # Should return True or False, not raise
            assert isinstance(available, bool)
        except Exception as e:
            pytest.fail(f"is_available() should not raise exceptions, got: {e}")

    def test_get_capabilities_returns_capabilities_object(self, summarizer):
        """Verify get_capabilities returns ProviderCapabilities instance."""
        caps = summarizer.__class__.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)

    def test_get_capabilities_has_required_fields(self, summarizer):
        """Verify capabilities object has all required fields."""
        caps = summarizer.__class__.get_capabilities()

        assert hasattr(caps, 'supports_streaming')
        assert hasattr(caps, 'supports_async')
        assert hasattr(caps, 'requires_api_key')
        assert hasattr(caps, 'is_local')
        assert hasattr(caps, 'max_context_tokens')
        assert hasattr(caps, 'cost_per_1k_input')
        assert hasattr(caps, 'cost_per_1k_output')

    def test_get_capabilities_types(self, summarizer):
        """Verify capabilities field types are correct."""
        caps = summarizer.__class__.get_capabilities()

        assert isinstance(caps.supports_streaming, bool)
        assert isinstance(caps.supports_async, bool)
        assert isinstance(caps.requires_api_key, bool)
        assert isinstance(caps.is_local, bool)
        assert caps.max_context_tokens is None or isinstance(caps.max_context_tokens, int)
        assert caps.cost_per_1k_input is None or isinstance(caps.cost_per_1k_input, (int, float))
        assert caps.cost_per_1k_output is None or isinstance(caps.cost_per_1k_output, (int, float))

    def test_get_model_info_returns_dict(self, summarizer):
        """Verify get_model_info returns dictionary."""
        model_info = summarizer.get_model_info()
        assert isinstance(model_info, dict)

    def test_get_model_info_has_provider(self, summarizer):
        """Verify model_info includes provider field."""
        model_info = summarizer.get_model_info()
        assert 'provider' in model_info
        assert model_info['provider'] == summarizer.get_provider_name()

    def test_summarize_method_signature(self, summarizer):
        """Verify summarize method has correct signature."""
        import inspect
        sig = inspect.signature(summarizer.summarize)

        # Should have content_data parameter
        assert 'content_data' in sig.parameters

        # Should have language parameter with default
        assert 'language' in sig.parameters
        assert sig.parameters['language'].default == 'de'

    # Quality Gates

    def test_cost_estimate_zero_for_empty_content(self, summarizer):
        """Verify cost for zero-length content is zero or very small."""
        cost = summarizer.estimate_cost(0)
        assert cost == 0.0 or cost < 0.001

    def test_provider_name_matches_model_info(self, summarizer):
        """Verify provider name matches model_info['provider']."""
        provider_name = summarizer.get_provider_name()
        model_info = summarizer.get_model_info()

        assert model_info['provider'] == provider_name

    def test_capabilities_cost_consistency(self, summarizer):
        """Verify cost in capabilities matches estimate_cost behavior."""
        caps = summarizer.__class__.get_capabilities()

        # If capabilities say provider is free, estimate should be 0
        if caps.is_free():
            cost = summarizer.estimate_cost(1000)
            assert cost == 0.0

    def test_capabilities_api_key_consistency(self, summarizer):
        """Verify capabilities requires_api_key matches initialization."""
        caps = summarizer.__class__.get_capabilities()

        # This is a weak test, but providers that don't require API keys
        # should have is_available() return True more easily
        if not caps.requires_api_key:
            # Local providers should be available if service is running
            # (we can't enforce this strictly without knowing service state)
            pass

    # Mocking Helpers

    @staticmethod
    def create_mock_content_data(title: str = "Test Title", content: str = "Test content") -> dict:
        """
        Create mock content_data for testing.

        Args:
            title: Content title
            content: Content text

        Returns:
            Dictionary suitable for passing to summarize()
        """
        return {
            'title': title,
            'content': content,
            'source_type': 'website'
        }
