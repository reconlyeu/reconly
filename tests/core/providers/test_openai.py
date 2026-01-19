"""Tests for OpenAI summarizer."""
import pytest
from unittest.mock import patch, Mock

from reconly_core.providers.openai_provider import OpenAIProvider
from tests.core.providers.base_test_suite import BaseProviderTestSuite


class TestOpenAIProvider(BaseProviderTestSuite):
    """Test suite for OpenAIProvider (inherits contract tests from BaseProviderTestSuite)."""

    @pytest.fixture
    def summarizer(self):
        """Return configured OpenAI summarizer instance."""
        return OpenAIProvider(api_key='test-openai-key-12345')

    # Provider-specific tests

    def test_initialization_with_api_key(self):
        """Test initialization with API key."""
        summarizer = OpenAIProvider(api_key='test-key')
        assert summarizer.api_key == 'test-key'
        assert summarizer.model == 'gpt-4-turbo'

    def test_initialization_with_custom_model(self):
        """Test initialization with custom model."""
        summarizer = OpenAIProvider(api_key='test-key', model='gpt-3.5-turbo')
        assert summarizer.model == 'gpt-3.5-turbo'

    def test_initialization_from_env_var(self, monkeypatch):
        """Test that API key is read from environment variable."""
        monkeypatch.setenv('OPENAI_API_KEY', 'env-key-12345')
        summarizer = OpenAIProvider()
        assert summarizer.api_key == 'env-key-12345'

    def test_initialization_missing_api_key(self):
        """Test that initialization fails without API key."""
        with pytest.raises(ValueError) as exc_info:
            OpenAIProvider()

        assert 'API key required' in str(exc_info.value)
        assert 'OPENAI_API_KEY' in str(exc_info.value)

    def test_initialization_with_base_url(self, monkeypatch):
        """Test initialization with custom base URL."""
        monkeypatch.setenv('OPENAI_BASE_URL', 'http://localhost:8080/v1')
        summarizer = OpenAIProvider(api_key='test-key')
        assert summarizer.base_url == 'http://localhost:8080/v1'

    def test_initialization_custom_base_url_parameter(self):
        """Test initialization with base_url parameter."""
        summarizer = OpenAIProvider(
            api_key='test-key',
            base_url='http://custom-endpoint:1234/v1'
        )
        assert summarizer.base_url == 'http://custom-endpoint:1234/v1'

    def test_get_provider_name(self):
        """Test provider name."""
        summarizer = OpenAIProvider(api_key='test-key')
        assert summarizer.get_provider_name() == 'openai'

    def test_get_model_info(self):
        """Test model info."""
        summarizer = OpenAIProvider(api_key='test-key', model='gpt-4')
        info = summarizer.get_model_info()

        assert info['provider'] == 'openai'
        assert info['model'] == 'gpt-4'

    def test_get_model_info_with_base_url(self):
        """Test model info includes base URL for compatible endpoints."""
        summarizer = OpenAIProvider(
            api_key='test-key',
            base_url='http://localhost:8080/v1'
        )
        info = summarizer.get_model_info()

        assert 'base_url' in info
        assert info['compatible_endpoint'] is True

    def test_estimate_cost_oss_edition(self):
        """Test cost estimation returns 0.0 in OSS edition (costs stubbed)."""
        summarizer = OpenAIProvider(api_key='test-key', model='gpt-4-turbo')

        # OSS edition stubs all costs to 0.0
        cost = summarizer.estimate_cost(1000)
        assert cost == 0.0

    def test_estimate_cost_consistent_across_models(self):
        """Test cost estimation is stubbed to 0.0 for all models in OSS."""
        summarizer_gpt4 = OpenAIProvider(api_key='test-key', model='gpt-4-turbo')
        summarizer_gpt35 = OpenAIProvider(api_key='test-key', model='gpt-3.5-turbo')

        # Both should return 0.0 in OSS
        assert summarizer_gpt4.estimate_cost(1000) == 0.0
        assert summarizer_gpt35.estimate_cost(1000) == 0.0

    def test_estimate_cost_consistent_across_lengths(self):
        """Test cost estimation is stubbed to 0.0 regardless of content length."""
        summarizer = OpenAIProvider(api_key='test-key')

        cost_small = summarizer.estimate_cost(100)
        cost_large = summarizer.estimate_cost(10000)

        # Both should be 0.0 in OSS edition
        assert cost_small == 0.0
        assert cost_large == 0.0

    def test_get_capabilities(self):
        """Test provider capabilities in OSS edition (costs stubbed to 0.0)."""
        caps = OpenAIProvider.get_capabilities()

        assert caps.requires_api_key is True
        assert caps.is_local is False
        # OSS edition stubs costs to 0.0
        assert caps.cost_per_1k_input == 0.0
        assert caps.cost_per_1k_output == 0.0
        assert caps.is_free() is True  # 0.0 cost means free in OSS

    def test_is_available_with_api_key(self):
        """Test is_available returns True when API key is set."""
        summarizer = OpenAIProvider(api_key='test-key')
        assert summarizer.is_available() is True

    def test_is_available_without_api_key(self, monkeypatch):
        """Test is_available returns False without API key."""
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)

        # Create with None API key (should fail validation but not crash is_available)
        try:
            summarizer = OpenAIProvider(api_key='test-key')
            # Manually set to None to test
            summarizer.api_key = None
            assert summarizer.is_available() is False
        except ValueError:
            # Expected if __init__ validates
            pass

    def test_validate_config_success(self):
        """Test validate_config returns empty list for valid config."""
        summarizer = OpenAIProvider(api_key='test-key-valid', model='gpt-4')
        errors = summarizer.validate_config()

        assert isinstance(errors, list)
        assert len(errors) == 0

    def test_validate_config_missing_api_key(self):
        """Test validate_config catches missing API key."""
        summarizer = OpenAIProvider(api_key='test-key')
        summarizer.api_key = None  # Manually clear

        errors = summarizer.validate_config()

        assert len(errors) > 0
        assert any('API key' in err for err in errors)

    def test_validate_config_invalid_base_url(self):
        """Test validate_config catches invalid base URL."""
        summarizer = OpenAIProvider(api_key='test-key')
        summarizer.base_url = 'invalid-url'

        errors = summarizer.validate_config()

        assert len(errors) > 0
        assert any('http://' in err or 'https://' in err for err in errors)

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_success(self, mock_openai_class):
        """Test successful summarization."""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock completion response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='This is a test summary.'))]
        mock_response.usage = Mock(prompt_tokens=250, completion_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        summarizer = OpenAIProvider(api_key='test-key')
        content_data = self.create_mock_content_data(
            title='Test Article',
            content='This is test content for summarization.'
        )

        result = summarizer.summarize(content_data, language='en')

        assert 'summary' in result
        assert result['summary'] == 'This is a test summary.'
        assert result['summary_language'] == 'en'
        assert 'estimated_cost' in result
        # OSS edition stubs costs to 0.0
        assert result['estimated_cost'] == 0.0

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_german(self, mock_openai_class):
        """Test summarization in German."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='Dies ist eine Testzusammenfassung.'))]
        mock_response.usage = Mock(prompt_tokens=250, completion_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        summarizer = OpenAIProvider(api_key='test-key')
        content_data = self.create_mock_content_data(
            title='Test Artikel',
            content='Dies ist ein Testinhalt.'
        )

        result = summarizer.summarize(content_data, language='de')

        assert result['summary_language'] == 'de'
        assert 'Dies ist' in result['summary']

    @patch('openai.OpenAI')
    def test_summarize_empty_content(self, mock_openai_class):
        """Test that summarize raises error for empty content."""
        summarizer = OpenAIProvider(api_key='test-key')
        content_data = self.create_mock_content_data(title='Test', content='')

        with pytest.raises(ValueError) as exc_info:
            summarizer.summarize(content_data)

        assert 'No content to summarize' in str(exc_info.value)

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_rate_limit_error(self, mock_openai_class):
        """Test summarize handles rate limit errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception('rate_limit exceeded')

        summarizer = OpenAIProvider(api_key='test-key')
        content_data = self.create_mock_content_data()

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert 'rate limit' in str(exc_info.value).lower()

    @patch('openai.OpenAI')
    def test_summarize_authentication_error(self, mock_openai_class):
        """Test summarize handles authentication errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception('authentication failed')

        summarizer = OpenAIProvider(api_key='invalid-key')
        content_data = self.create_mock_content_data()

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert 'authentication' in str(exc_info.value).lower()

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_model_not_found(self, mock_openai_class):
        """Test summarize handles model not found errors."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_client.chat.completions.create.side_effect = Exception('model not found')

        summarizer = OpenAIProvider(api_key='test-key', model='gpt-nonexistent')
        content_data = self.create_mock_content_data()

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert 'model' in str(exc_info.value).lower()
        assert 'not found' in str(exc_info.value).lower()

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_uses_centralized_prompts(self, mock_openai_class):
        """Test that summarize uses centralized prompts."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='Summary'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        summarizer = OpenAIProvider(api_key='test-key')
        content_data = self.create_mock_content_data()
        summarizer.summarize(content_data, language='de')

        # Check that create was called with messages
        assert mock_client.chat.completions.create.called
        call_args = mock_client.chat.completions.create.call_args
        assert 'messages' in call_args.kwargs
        messages = call_args.kwargs['messages']
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_different_models(self, mock_openai_class):
        """Test summarization with different models."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='Summary'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        models = ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo']
        for model in models:
            summarizer = OpenAIProvider(api_key='test-key', model=model)
            content_data = self.create_mock_content_data()
            result = summarizer.summarize(content_data)

            assert 'summary' in result

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_summarize_calculates_cost_in_oss(self, mock_openai_class):
        """Test that summarize returns 0.0 cost in OSS edition (costs stubbed)."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        # Mock response with specific token usage
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='Summary'))]
        mock_response.usage = Mock(prompt_tokens=1000, completion_tokens=500)
        mock_client.chat.completions.create.return_value = mock_response

        summarizer = OpenAIProvider(api_key='test-key', model='gpt-4-turbo')
        content_data = self.create_mock_content_data()
        result = summarizer.summarize(content_data)

        # OSS edition stubs all costs to 0.0
        # Enterprise edition would calculate: (1000/1M * 10) + (500/1M * 30) = 0.025
        assert result['estimated_cost'] == 0.0

    def test_model_pricing_dictionary(self):
        """Test that MODEL_PRICING contains expected models."""
        pricing = OpenAIProvider.MODEL_PRICING

        assert 'gpt-4' in pricing
        assert 'gpt-4-turbo' in pricing
        assert 'gpt-3.5-turbo' in pricing

        # Check pricing format (input_rate, output_rate)
        for model, rates in pricing.items():
            assert len(rates) == 2
            assert all(isinstance(r, (int, float)) for r in rates)

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_compatible_endpoint_usage(self, mock_openai_class):
        """Test using OpenAI-compatible endpoint."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='Summary from LocalAI'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_client.chat.completions.create.return_value = mock_response

        # Test with LocalAI-compatible endpoint
        summarizer = OpenAIProvider(
            api_key='dummy-key',
            base_url='http://localhost:8080/v1'
        )
        content_data = self.create_mock_content_data()
        result = summarizer.summarize(content_data)

        assert 'summary' in result
        assert result['summary'] == 'Summary from LocalAI'

        # Verify client was initialized with custom base_url
        mock_openai_class.assert_called()
        init_call = mock_openai_class.call_args
        assert init_call.kwargs['base_url'] == 'http://localhost:8080/v1'
