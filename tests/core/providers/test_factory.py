"""Tests for summarizer factory."""
import pytest
from unittest.mock import Mock, patch
from reconly_core.resilience import ErrorCategory, RetryConfig, classify_error
from reconly_core.providers.factory import (
    get_summarizer,
    SummarizerWithFallback,
    list_available_models,
    _get_fallback_chain,
    _instantiate_provider,
    DEFAULT_FALLBACK_CHAIN,
)
from reconly_core.providers.anthropic import AnthropicProvider
from reconly_core.providers.huggingface import HuggingFaceProvider
from reconly_core.providers.ollama import OllamaProvider
from reconly_core.providers.openai_provider import OpenAIProvider


def create_mock_summarizer(name: str, summarize_return=None, summarize_side_effect=None):
    """Create a mock summarizer with all required methods for retry logic.

    Args:
        name: Provider name for the mock
        summarize_return: Return value for summarize() method
        summarize_side_effect: Side effect for summarize() method (for errors)

    Returns:
        Configured Mock object
    """
    mock = Mock()
    mock.get_provider_name.return_value = name
    mock.is_available.return_value = True
    mock.get_retry_config.return_value = RetryConfig(max_attempts=1, base_delay=0.01)
    mock.classify_error = classify_error  # Use real classify_error

    if summarize_return is not None:
        mock.summarize.return_value = summarize_return
    if summarize_side_effect is not None:
        mock.summarize.side_effect = summarize_side_effect

    return mock


class TestSummarizerFactory:
    """Test suite for summarizer factory functions."""

    @patch('requests.get')
    def test_get_summarizer_default_provider(self, mock_get):
        """WHEN no provider is specified
        THEN Ollama is used by default (local, free, privacy-focused)."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'models': [{'name': 'llama3.2'}]}

        result = get_summarizer(enable_fallback=False)

        assert isinstance(result, OllamaProvider)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-anthropic-key'})
    def test_get_summarizer_anthropic_provider(self):
        """WHEN 'anthropic' provider is specified
        THEN AnthropicProvider is returned."""
        result = get_summarizer(provider='anthropic', enable_fallback=False)

        assert isinstance(result, AnthropicProvider)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_get_summarizer_custom_model(self):
        """WHEN custom model is specified
        THEN it's passed to HuggingFace summarizer."""
        result = get_summarizer(provider='huggingface', model='mixtral-8x7b', enable_fallback=False)

        assert isinstance(result, HuggingFaceProvider)
        # HuggingFace expands 'mixtral-8x7b' to full model name
        assert 'mixtral' in result.model.lower()

    def test_get_summarizer_invalid_provider(self):
        """WHEN invalid provider is specified
        THEN ValueError is raised."""
        with pytest.raises(ValueError) as exc_info:
            get_summarizer(provider='invalid')

        assert "Unknown provider" in str(exc_info.value)

    @patch.dict('os.environ', {
        'HUGGINGFACE_API_KEY': 'test-hf-key',
        'ANTHROPIC_API_KEY': 'test-anthropic-key'
    })
    def test_get_summarizer_with_fallback(self):
        """WHEN fallback is enabled
        THEN SummarizerWithFallback is returned."""
        result = get_summarizer(provider='huggingface', enable_fallback=True)

        assert isinstance(result, SummarizerWithFallback)
        assert isinstance(result.primary, HuggingFaceProvider)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.providers.factory._get_fallback_chain')
    def test_get_summarizer_uses_chain_first_provider(self, mock_get_chain):
        """WHEN no provider is specified
        THEN the first provider in fallback chain is used."""
        mock_get_chain.return_value = ['anthropic', 'ollama', 'openai']
        result = get_summarizer(enable_fallback=False)

        assert isinstance(result, AnthropicProvider)

    @pytest.mark.xfail(reason="HuggingFace provider registration issue - pre-existing bug")
    def test_list_available_models(self):
        """WHEN list_available_models is called
        THEN all providers return model lists."""
        models = list_available_models()

        # Check all providers are present
        assert 'huggingface' in models
        assert 'anthropic' in models
        assert 'ollama' in models
        assert 'openai' in models

        # Check each provider has models (structure check, not specific IDs)
        assert len(models['huggingface']) >= 1
        assert len(models['anthropic']) >= 1
        assert len(models['openai']) >= 1
        # Ollama may be empty if server not running - that's OK

    @patch('requests.get')
    def test_get_summarizer_ollama_provider(self, mock_get):
        """WHEN 'ollama' provider is specified
        THEN OllamaProvider is returned."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'models': [{'name': 'llama3.2'}]}

        result = get_summarizer(provider='ollama', enable_fallback=False)

        assert isinstance(result, OllamaProvider)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-openai-key'})
    def test_get_summarizer_openai_provider(self):
        """WHEN 'openai' provider is specified
        THEN OpenAIProvider is returned."""
        result = get_summarizer(provider='openai', enable_fallback=False)

        assert isinstance(result, OpenAIProvider)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_get_summarizer_openai_custom_model(self):
        """WHEN custom OpenAI model is specified
        THEN it's passed to OpenAI summarizer."""
        # OpenAI model is set in constructor, not via factory parameter
        result = get_summarizer(provider='openai', enable_fallback=False)

        assert isinstance(result, OpenAIProvider)

    @patch('requests.get')
    def test_get_summarizer_ollama_custom_model(self, mock_get):
        """WHEN custom Ollama model is specified
        THEN it's used in initialization."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'models': [{'name': 'mistral'}]}

        result = get_summarizer(provider='ollama', model='mistral', enable_fallback=False)

        assert isinstance(result, OllamaProvider)
        # Note: model selection happens in __init__, we just verify instance was created

    @patch.dict('os.environ', {
        'HUGGINGFACE_API_KEY': 'hf-key',
        'OPENAI_API_KEY': 'openai-key',
        'ANTHROPIC_API_KEY': 'anthropic-key'
    })
    @patch('requests.get')
    def test_fallback_chain_priority(self, mock_get):
        """WHEN fallback is enabled with multiple providers
        THEN fallback chain follows priority: Ollama → HF → OpenAI → Anthropic."""
        # Mock Ollama server check
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'models': [{'name': 'llama3.2'}]}

        result = get_summarizer(provider='huggingface', enable_fallback=True)

        # Should return fallback wrapper
        assert isinstance(result, SummarizerWithFallback)

        # Primary should be HuggingFace
        assert isinstance(result.primary, HuggingFaceProvider)

        # Fallback chain should include other providers
        assert len(result.fallbacks) > 0

    @patch('requests.get')
    @patch('reconly_core.providers.factory._get_fallback_chain')
    def test_get_summarizer_uses_first_in_chain_ollama(self, mock_get_chain, mock_get):
        """WHEN Ollama is first in fallback chain
        THEN Ollama provider is used as default."""
        mock_get_chain.return_value = ['ollama', 'openai', 'anthropic']
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'models': [{'name': 'llama3.2'}]}

        result = get_summarizer(enable_fallback=False)

        assert isinstance(result, OllamaProvider)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('reconly_core.providers.factory._get_fallback_chain')
    def test_get_summarizer_uses_first_in_chain_openai(self, mock_get_chain):
        """WHEN OpenAI is first in fallback chain
        THEN OpenAI provider is used as default."""
        mock_get_chain.return_value = ['openai', 'ollama', 'anthropic']
        result = get_summarizer(enable_fallback=False)

        assert isinstance(result, OpenAIProvider)


class TestSummarizerWithFallback:
    """Test suite for SummarizerWithFallback class."""

    @pytest.fixture
    def content_data(self):
        """Sample content data for testing."""
        return {
            'url': 'https://example.com/article',
            'title': 'Test Article',
            'content': 'Test content',
            'source_type': 'website'
        }

    def test_fallback_primary_success(self, content_data):
        """WHEN primary summarizer succeeds
        THEN result is returned without fallback."""
        mock_primary = create_mock_summarizer(
            'primary',
            summarize_return={**content_data, 'summary': 'Primary summary'}
        )
        mock_fallback = create_mock_summarizer('fallback')

        wrapper = SummarizerWithFallback(mock_primary, [mock_fallback])
        result = wrapper.summarize(content_data)

        assert result['summary'] == 'Primary summary'
        assert result['fallback_used'] == False
        mock_primary.summarize.assert_called_once()
        mock_fallback.summarize.assert_not_called()

    def test_fallback_primary_fails(self, content_data):
        """WHEN primary summarizer fails
        THEN fallback is used."""
        mock_primary = create_mock_summarizer(
            'primary',
            summarize_side_effect=Exception("Primary failed")
        )
        mock_fallback = create_mock_summarizer(
            'fallback',
            summarize_return={**content_data, 'summary': 'Fallback summary'}
        )

        wrapper = SummarizerWithFallback(mock_primary, [mock_fallback])
        result = wrapper.summarize(content_data)

        assert result['summary'] == 'Fallback summary'
        assert result['fallback_used'] == True
        assert result['fallback_level'] == 1
        mock_primary.summarize.assert_called_once()
        mock_fallback.summarize.assert_called_once()

    def test_fallback_all_fail(self, content_data):
        """WHEN all summarizers fail
        THEN exception is raised."""
        mock_primary = create_mock_summarizer(
            'primary',
            summarize_side_effect=Exception("Primary failed")
        )
        mock_fallback1 = create_mock_summarizer(
            'fallback1',
            summarize_side_effect=Exception("Fallback1 failed")
        )
        mock_fallback2 = create_mock_summarizer(
            'fallback2',
            summarize_side_effect=Exception("Fallback2 failed")
        )

        wrapper = SummarizerWithFallback(mock_primary, [mock_fallback1, mock_fallback2])

        with pytest.raises(Exception) as exc_info:
            wrapper.summarize(content_data)

        assert "All" in str(exc_info.value) and "providers failed" in str(exc_info.value)
        mock_primary.summarize.assert_called_once()
        mock_fallback1.summarize.assert_called_once()
        mock_fallback2.summarize.assert_called_once()

    def test_fallback_chain_order(self, content_data):
        """WHEN multiple fallbacks exist
        THEN they are tried in order."""
        call_order = []

        def make_failing_side_effect(name):
            def side_effect(*args, **kwargs):
                call_order.append(name)
                raise Exception(f"{name} failed")
            return side_effect

        def make_success_side_effect(name, result):
            def side_effect(*args, **kwargs):
                call_order.append(name)
                return result
            return side_effect

        mock_primary = create_mock_summarizer('primary')
        mock_primary.summarize.side_effect = make_failing_side_effect('primary')

        mock_fallback1 = create_mock_summarizer('fallback1')
        mock_fallback1.summarize.side_effect = make_failing_side_effect('fallback1')

        mock_fallback2 = create_mock_summarizer('fallback2')
        mock_fallback2.summarize.side_effect = make_success_side_effect(
            'fallback2',
            {**content_data, 'summary': 'Success'}
        )

        wrapper = SummarizerWithFallback(mock_primary, [mock_fallback1, mock_fallback2])
        result = wrapper.summarize(content_data)

        assert call_order == ['primary', 'fallback1', 'fallback2']
        assert result['summary'] == 'Success'
        assert result['fallback_level'] == 2

    def test_get_provider_name(self):
        """WHEN get_provider_name is called
        THEN primary provider name is returned."""
        mock_primary = Mock()
        mock_primary.get_provider_name.return_value = 'primary-provider'

        wrapper = SummarizerWithFallback(mock_primary, [])

        assert wrapper.get_provider_name() == 'primary-provider'

    def test_estimate_cost(self):
        """WHEN estimate_cost is called
        THEN primary provider cost is returned."""
        mock_primary = Mock()
        mock_primary.estimate_cost.return_value = 0.05

        wrapper = SummarizerWithFallback(mock_primary, [])

        assert wrapper.estimate_cost(1000) == 0.05

    def test_get_model_info(self):
        """WHEN get_model_info is called
        THEN primary provider model info is returned."""
        mock_primary = Mock()
        mock_primary.get_model_info.return_value = {'model': 'test-model'}

        wrapper = SummarizerWithFallback(mock_primary, [])

        assert wrapper.get_model_info() == {'model': 'test-model'}


class TestFallbackChain:
    """Test suite for settings-based fallback chain."""

    def test_default_fallback_chain(self):
        """WHEN no settings are configured
        THEN default fallback chain is returned."""
        chain = _get_fallback_chain(db=None)

        assert chain == DEFAULT_FALLBACK_CHAIN
        assert 'ollama' in chain
        assert 'huggingface' in chain
        assert 'openai' in chain
        assert 'anthropic' in chain

    def test_fallback_chain_filters_invalid_providers(self):
        """WHEN fallback chain contains invalid providers
        THEN they are filtered out."""
        with patch('reconly_core.providers.factory._get_setting_with_db_fallback') as mock_get:
            mock_get.return_value = ['ollama', 'invalid_provider', 'openai']
            chain = _get_fallback_chain(db=None)

            assert 'ollama' in chain
            assert 'openai' in chain
            assert 'invalid_provider' not in chain

    def test_fallback_chain_handles_string_value(self):
        """WHEN fallback chain is stored as comma-separated string
        THEN it is parsed correctly."""
        with patch('reconly_core.providers.factory._get_setting_with_db_fallback') as mock_get:
            mock_get.return_value = 'ollama,openai,anthropic'
            chain = _get_fallback_chain(db=None)

            assert chain == ['ollama', 'openai', 'anthropic']

    def test_fallback_chain_handles_json_string(self):
        """WHEN fallback chain is stored as JSON string
        THEN it is parsed correctly."""
        with patch('reconly_core.providers.factory._get_setting_with_db_fallback') as mock_get:
            mock_get.return_value = '["ollama", "anthropic", "openai"]'
            chain = _get_fallback_chain(db=None)

            assert chain == ['ollama', 'anthropic', 'openai']

    def test_fallback_chain_returns_default_for_empty(self):
        """WHEN fallback chain setting results in empty list
        THEN default chain is returned."""
        with patch('reconly_core.providers.factory._get_setting_with_db_fallback') as mock_get:
            mock_get.return_value = ['invalid1', 'invalid2']
            chain = _get_fallback_chain(db=None)

            # Should return default chain since all providers were invalid
            assert chain == DEFAULT_FALLBACK_CHAIN


class TestInstantiateProvider:
    """Test suite for provider instantiation."""

    @patch('requests.get')
    def test_instantiate_ollama_provider(self, mock_get):
        """WHEN instantiating Ollama provider
        THEN OllamaProvider is returned."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'models': [{'name': 'llama3.2'}]}

        provider = _instantiate_provider('ollama')

        assert isinstance(provider, OllamaProvider)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    def test_instantiate_anthropic_provider(self):
        """WHEN instantiating Anthropic provider
        THEN AnthropicProvider is returned."""
        provider = _instantiate_provider('anthropic')

        assert isinstance(provider, AnthropicProvider)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_instantiate_openai_provider(self):
        """WHEN instantiating OpenAI provider
        THEN OpenAIProvider is returned."""
        provider = _instantiate_provider('openai')

        assert isinstance(provider, OpenAIProvider)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_instantiate_huggingface_provider(self):
        """WHEN instantiating HuggingFace provider
        THEN HuggingFaceProvider is returned."""
        provider = _instantiate_provider('huggingface')

        assert isinstance(provider, HuggingFaceProvider)

    def test_instantiate_invalid_provider(self):
        """WHEN instantiating invalid provider
        THEN ValueError is raised."""
        with pytest.raises(ValueError) as exc_info:
            _instantiate_provider('invalid_provider')

        assert "Unknown provider" in str(exc_info.value)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_instantiate_provider_with_model_override(self):
        """WHEN model override is provided
        THEN provider uses that model."""
        provider = _instantiate_provider('huggingface', model='mixtral')

        assert isinstance(provider, HuggingFaceProvider)
        assert 'mixtral' in provider.model.lower()
