"""Tests for Ollama summarizer."""
import pytest
from unittest.mock import patch, Mock
import requests

from reconly_core.providers.ollama import OllamaProvider
from tests.core.providers.base_test_suite import BaseProviderTestSuite


class TestOllamaProvider(BaseProviderTestSuite):
    """Test suite for OllamaProvider (inherits contract tests from BaseProviderTestSuite)."""

    @pytest.fixture
    def summarizer(self):
        """Return configured Ollama summarizer instance."""
        with patch('requests.get') as mock_get:
            # Mock successful Ollama server check
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [
                    {'name': 'llama3.2'},
                    {'name': 'mistral'}
                ]
            }
            return OllamaProvider(model='llama3.2')

    # Provider-specific tests

    def test_initialization_default_base_url(self):
        """Test that default base URL is set correctly."""
        with patch('requests.get'):
            summarizer = OllamaProvider()
            assert summarizer.base_url == 'http://localhost:11434'

    def test_initialization_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch('requests.get'):
            summarizer = OllamaProvider(base_url='http://192.168.1.100:11434')
            assert summarizer.base_url == 'http://192.168.1.100:11434'

    def test_initialization_from_env_var(self, monkeypatch):
        """Test that base URL is read from environment variable."""
        monkeypatch.setenv('OLLAMA_BASE_URL', 'http://custom:11434')
        with patch('requests.get'):
            summarizer = OllamaProvider()
            assert summarizer.base_url == 'http://custom:11434'

    def test_initialization_auto_detects_models(self):
        """Test that initialization auto-detects available models."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [
                    {'name': 'llama3.2'},
                    {'name': 'mistral'},
                    {'name': 'gemma2'}
                ]
            }

            summarizer = OllamaProvider()

            # Should use first available model
            assert summarizer.model in ['llama3.2', 'mistral', 'gemma2']

    def test_initialization_uses_specified_model(self):
        """Test initialization with specified model."""
        with patch('requests.get'):
            summarizer = OllamaProvider(model='mistral')
            assert summarizer.model == 'mistral'

    def test_get_provider_name(self):
        """Test provider name."""
        with patch('requests.get'):
            summarizer = OllamaProvider()
            assert summarizer.get_provider_name() == 'ollama'

    def test_get_model_info(self):
        """Test model info includes local flag."""
        with patch('requests.get'):
            summarizer = OllamaProvider(model='llama3.2')
            info = summarizer.get_model_info()

            assert info['provider'] == 'ollama'
            assert info['model'] == 'llama3.2'
            assert info['local'] is True

    def test_estimate_cost_always_zero(self):
        """Test that cost estimation always returns 0.0 for local models."""
        with patch('requests.get'):
            summarizer = OllamaProvider()

            assert summarizer.estimate_cost(100) == 0.0
            assert summarizer.estimate_cost(10000) == 0.0
            assert summarizer.estimate_cost(1000000) == 0.0

    def test_get_capabilities_is_local(self):
        """Test capabilities indicate local provider."""
        caps = OllamaProvider.get_capabilities()

        assert caps.is_local is True
        assert caps.requires_api_key is False
        assert caps.cost_per_1k_input == 0.0
        assert caps.cost_per_1k_output == 0.0
        assert caps.is_free() is True

    def test_is_available_when_server_running(self):
        """Test is_available returns True when Ollama server is running."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200

            summarizer = OllamaProvider()
            assert summarizer.is_available() is True

    def test_is_available_when_server_not_running(self):
        """Test is_available returns False when Ollama server is not reachable."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError("Connection refused")

            summarizer = OllamaProvider()
            assert summarizer.is_available() is False

    def test_is_available_does_not_raise_exception(self):
        """Test is_available never raises exceptions."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Unexpected error")

            summarizer = OllamaProvider()
            # Should return False, not raise
            assert summarizer.is_available() is False

    def test_validate_config_success(self):
        """Test validate_config returns empty list for valid config."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [{'name': 'llama3.2'}]
            }

            summarizer = OllamaProvider(model='llama3.2')
            errors = summarizer.validate_config()

            assert isinstance(errors, list)
            assert len(errors) == 0

    def test_validate_config_invalid_url(self):
        """Test validate_config catches invalid base URL."""
        with patch('requests.get'):
            summarizer = OllamaProvider(base_url='invalid-url')
            errors = summarizer.validate_config()

            assert len(errors) > 0
            assert any('http://' in err or 'https://' in err for err in errors)

    def test_validate_config_server_unreachable(self):
        """Test validate_config reports when server is unreachable."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError()

            summarizer = OllamaProvider()
            errors = summarizer.validate_config()

            assert len(errors) > 0
            assert any('not reachable' in err.lower() for err in errors)

    def test_validate_config_model_not_available(self):
        """Test validate_config reports when model is not available."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [{'name': 'llama3.2'}]
            }

            summarizer = OllamaProvider(model='nonexistent-model')
            errors = summarizer.validate_config()

            assert len(errors) > 0
            assert any('not available' in err.lower() for err in errors)

    @patch('requests.post')
    def test_summarize_success(self, mock_post):
        """Test successful summarization."""
        with patch('requests.get'):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'response': 'This is a test summary.',
                'done': True
            }

            summarizer = OllamaProvider(model='llama3.2')
            content_data = self.create_mock_content_data(
                title='Test Article',
                content='This is test content for summarization.'
            )

            result = summarizer.summarize(content_data, language='en')

            assert 'summary' in result
            assert result['summary'] == 'This is a test summary.'
            assert result['summary_language'] == 'en'
            assert result['estimated_cost'] == 0.0

    @patch('requests.post')
    def test_summarize_german(self, mock_post):
        """Test summarization in German."""
        with patch('requests.get'):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'response': 'Dies ist eine Testzusammenfassung.',
                'done': True
            }

            summarizer = OllamaProvider(model='llama3.2')
            content_data = self.create_mock_content_data(
                title='Test Artikel',
                content='Dies ist ein Testinhalt.'
            )

            result = summarizer.summarize(content_data, language='de')

            assert result['summary_language'] == 'de'
            assert 'Dies ist' in result['summary']

    @patch('requests.post')
    def test_summarize_empty_content(self, mock_post):
        """Test that summarize raises error for empty content."""
        with patch('requests.get'):
            summarizer = OllamaProvider()
            content_data = self.create_mock_content_data(title='Test', content='')

            with pytest.raises(ValueError) as exc_info:
                summarizer.summarize(content_data)

            assert 'No content to summarize' in str(exc_info.value)

    @patch('requests.post')
    def test_summarize_connection_error(self, mock_post):
        """Test summarize handles connection errors gracefully."""
        with patch('requests.get'):
            mock_post.side_effect = requests.ConnectionError("Connection refused")

            summarizer = OllamaProvider()
            content_data = self.create_mock_content_data()

            with pytest.raises(Exception) as exc_info:
                summarizer.summarize(content_data)

            assert 'Could not connect to Ollama' in str(exc_info.value)

    @patch('requests.post')
    def test_summarize_timeout(self, mock_post):
        """Test summarize handles timeout errors."""
        with patch('requests.get'):
            mock_post.side_effect = requests.Timeout("Request timed out")

            summarizer = OllamaProvider(timeout=30)
            content_data = self.create_mock_content_data()

            with pytest.raises(Exception) as exc_info:
                summarizer.summarize(content_data)

            assert 'timed out' in str(exc_info.value).lower()

    @patch('requests.post')
    def test_summarize_api_error(self, mock_post):
        """Test summarize handles API errors."""
        with patch('requests.get'):
            mock_post.return_value.status_code = 500
            mock_post.return_value.text = 'Internal server error'

            summarizer = OllamaProvider()
            content_data = self.create_mock_content_data()

            with pytest.raises(Exception) as exc_info:
                summarizer.summarize(content_data)

            assert 'Ollama API error' in str(exc_info.value)

    @patch('requests.post')
    def test_summarize_empty_response(self, mock_post):
        """Test summarize handles empty response from Ollama."""
        with patch('requests.get'):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'response': '',
                'done': True
            }

            summarizer = OllamaProvider()
            content_data = self.create_mock_content_data()

            with pytest.raises(Exception) as exc_info:
                summarizer.summarize(content_data)

            assert 'empty response' in str(exc_info.value).lower()

    @patch('requests.post')
    def test_summarize_uses_centralized_prompts(self, mock_post):
        """Test that summarize uses centralized prompts."""
        with patch('requests.get'):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'response': 'Summary',
                'done': True
            }

            summarizer = OllamaProvider()
            content_data = self.create_mock_content_data()
            summarizer.summarize(content_data, language='de')

            # Check that post was called with a prompt
            assert mock_post.called
            call_args = mock_post.call_args
            assert 'json' in call_args.kwargs
            assert 'prompt' in call_args.kwargs['json']

    @patch('requests.post')
    def test_summarize_configurable_timeout(self, mock_post):
        """Test that timeout is configurable."""
        with patch('requests.get'):
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'response': 'Summary'}

            summarizer = OllamaProvider(timeout=120)
            content_data = self.create_mock_content_data()
            summarizer.summarize(content_data)

            # Verify timeout was passed to requests
            call_args = mock_post.call_args
            assert call_args.kwargs['timeout'] == 120

    def test_fetch_available_models_success(self):
        """Test fetching available models from Ollama."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [
                    {'name': 'llama3.2'},
                    {'name': 'mistral'},
                    {'name': 'gemma2'}
                ]
            }

            summarizer = OllamaProvider()
            models = summarizer._fetch_available_models()

            assert 'llama3.2' in models
            assert 'mistral' in models
            assert 'gemma2' in models

    def test_fetch_available_models_server_down(self):
        """Test fetch_available_models returns empty list when server is down."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError()

            summarizer = OllamaProvider()
            models = summarizer._fetch_available_models()

            assert models == []
