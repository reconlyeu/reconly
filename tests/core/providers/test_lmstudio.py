"""Tests for LMStudio summarizer."""
import pytest
from unittest.mock import patch, MagicMock

from reconly_core.providers.lmstudio import LMStudioProvider
from tests.core.providers.base_test_suite import BaseProviderTestSuite


class TestLMStudioProvider(BaseProviderTestSuite):
    """Test suite for LMStudioProvider (inherits contract tests from BaseProviderTestSuite)."""

    @pytest.fixture
    def summarizer(self):
        """Return configured LMStudio summarizer instance."""
        with patch('requests.get') as mock_get:
            # Mock successful LMStudio server check
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': [
                    {'id': 'local-model-1'},
                    {'id': 'local-model-2'}
                ]
            }
            return LMStudioProvider(model='local-model-1')

    # Provider-specific tests

    def test_initialization_default_base_url(self):
        """Test that default base URL is set correctly."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            assert summarizer.base_url == 'http://localhost:1234/v1'

    def test_initialization_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(
                model='test-model',
                base_url='http://192.168.1.100:1234/v1'
            )
            assert summarizer.base_url == 'http://192.168.1.100:1234/v1'

    def test_initialization_from_env_var(self, monkeypatch):
        """Test that base URL is read from environment variable."""
        monkeypatch.setenv('LMSTUDIO_BASE_URL', 'http://custom:1234/v1')
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            assert summarizer.base_url == 'http://custom:1234/v1'

    def test_initialization_model_from_env_var(self, monkeypatch):
        """Test that model is read from environment variable."""
        monkeypatch.setenv('LMSTUDIO_MODEL', 'env-model')
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'data': []}
            summarizer = LMStudioProvider()
            assert summarizer.model == 'env-model'

    def test_initialization_auto_detects_models(self):
        """Test that initialization auto-detects available models."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': [
                    {'id': 'model-a'},
                    {'id': 'model-b'},
                    {'id': 'model-c'}
                ]
            }

            summarizer = LMStudioProvider()

            # Should use first available model
            assert summarizer.model in ['model-a', 'model-b', 'model-c']

    def test_initialization_uses_specified_model(self):
        """Test initialization with specified model."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='my-custom-model')
            assert summarizer.model == 'my-custom-model'

    def test_get_provider_name(self):
        """Test provider name."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            assert summarizer.get_provider_name() == 'lmstudio'

    def test_get_model_info(self):
        """Test model info includes local flag."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='local-model')
            info = summarizer.get_model_info()

            assert info['provider'] == 'lmstudio'
            assert info['model'] == 'local-model'
            assert info['local'] is True
            assert 'base_url' in info

    def test_estimate_cost_always_zero(self):
        """Test that cost estimation always returns 0.0 for local models."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')

            assert summarizer.estimate_cost(100) == 0.0
            assert summarizer.estimate_cost(10000) == 0.0
            assert summarizer.estimate_cost(1000000) == 0.0

    def test_get_capabilities_is_local(self):
        """Test capabilities indicate local provider."""
        caps = LMStudioProvider.get_capabilities()

        assert caps.is_local is True
        assert caps.requires_api_key is False
        assert caps.cost_per_1k_input == 0.0
        assert caps.cost_per_1k_output == 0.0
        assert caps.is_free() is True

    def test_is_available_when_server_running(self):
        """Test is_available returns True when LMStudio server is running."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200

            summarizer = LMStudioProvider(model='test-model')
            assert summarizer.is_available() is True

    def test_is_available_when_server_not_running(self):
        """Test is_available returns False when LMStudio server is not reachable."""
        with patch('requests.get') as mock_get:
            # First call for initialization
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'data': [{'id': 'test-model'}]}

            summarizer = LMStudioProvider(model='test-model')

            # Now make server unavailable for is_available check
            import requests
            mock_get.side_effect = requests.ConnectionError("Connection refused")

            assert summarizer.is_available() is False

    def test_is_available_does_not_raise_exception(self):
        """Test is_available never raises exceptions."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'data': [{'id': 'test-model'}]}

            summarizer = LMStudioProvider(model='test-model')

            # Make it raise on next call
            mock_get.side_effect = Exception("Unexpected error")

            # Should return False, not raise
            assert summarizer.is_available() is False

    def test_validate_config_success(self):
        """Test validate_config returns empty list for valid config."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': [{'id': 'test-model'}]
            }

            summarizer = LMStudioProvider(model='test-model')
            errors = summarizer.validate_config()

            assert isinstance(errors, list)
            assert len(errors) == 0

    def test_validate_config_invalid_url(self):
        """Test validate_config catches invalid base URL."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model', base_url='invalid-url')
            errors = summarizer.validate_config()

            assert len(errors) > 0
            assert any('http://' in err or 'https://' in err for err in errors)

    def test_validate_config_server_unreachable(self):
        """Test validate_config reports when server is unreachable."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError()

            summarizer = LMStudioProvider(model='test-model')
            errors = summarizer.validate_config()

            assert len(errors) > 0
            assert any('not reachable' in err.lower() for err in errors)

    def test_validate_config_model_not_available(self):
        """Test validate_config reports when model is not available."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': [{'id': 'other-model'}]
            }

            summarizer = LMStudioProvider(model='nonexistent-model')
            errors = summarizer.validate_config()

            assert len(errors) > 0
            assert any('not available' in err.lower() for err in errors)

    def test_validate_config_no_model_specified(self):
        """Test validate_config reports when no model is available."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'data': []}

            summarizer = LMStudioProvider()
            errors = summarizer.validate_config()

            # Should report that no model is available
            assert len(errors) > 0

    def test_summarize_success(self):
        """Test successful summarization."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 300

                # Create mock client
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = 'This is a test summary.'
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50

                mock_client.chat.completions.create.return_value = mock_response
                summarizer.client = mock_client

                content_data = self.create_mock_content_data(
                    title='Test Article',
                    content='This is test content for summarization.'
                )

                result = summarizer.summarize(content_data, language='en')

                assert 'summary' in result
                assert result['summary'] == 'This is a test summary.'
                assert result['summary_language'] == 'en'
                assert result['estimated_cost'] == 0.0

    def test_summarize_german(self):
        """Test summarization in German."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 300

                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = 'Dies ist eine Testzusammenfassung.'
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50

                mock_client.chat.completions.create.return_value = mock_response
                summarizer.client = mock_client

                content_data = self.create_mock_content_data(
                    title='Test Artikel',
                    content='Dies ist ein Testinhalt.'
                )

                result = summarizer.summarize(content_data, language='de')

                assert result['summary_language'] == 'de'
                assert 'Dies ist' in result['summary']

    def test_summarize_empty_content(self):
        """Test that summarize raises error for empty content."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            content_data = self.create_mock_content_data(title='Test', content='')

            with pytest.raises(ValueError) as exc_info:
                summarizer.summarize(content_data)

            assert 'No content to summarize' in str(exc_info.value)

    def test_summarize_no_model_raises_error(self):
        """Test that summarize raises error when no model is available."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'data': []}

            summarizer = LMStudioProvider()
            content_data = self.create_mock_content_data()

            with pytest.raises(ValueError) as exc_info:
                summarizer.summarize(content_data)

            assert 'No model available' in str(exc_info.value)

    def test_summarize_connection_error(self):
        """Test summarize handles connection errors gracefully."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 300

                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception(
                    "Connection refused"
                )
                summarizer.client = mock_client

                content_data = self.create_mock_content_data()

                with pytest.raises(Exception) as exc_info:
                    summarizer.summarize(content_data)

                assert 'Could not connect to LMStudio' in str(exc_info.value)

    def test_summarize_timeout(self):
        """Test summarize handles timeout errors."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 30

                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = Exception("timeout")
                summarizer.client = mock_client

                content_data = self.create_mock_content_data()

                with pytest.raises(Exception) as exc_info:
                    summarizer.summarize(content_data)

                assert 'timed out' in str(exc_info.value).lower()

    def test_summarize_empty_response(self):
        """Test summarize handles empty response from LMStudio."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 300

                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = ''
                mock_response.usage = None

                mock_client.chat.completions.create.return_value = mock_response
                summarizer.client = mock_client

                content_data = self.create_mock_content_data()

                with pytest.raises(Exception) as exc_info:
                    summarizer.summarize(content_data)

                assert 'empty response' in str(exc_info.value).lower()

    def test_summarize_uses_openai_sdk(self):
        """Test that summarize uses OpenAI SDK for API calls."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 300

                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = 'Summary'
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50

                mock_client.chat.completions.create.return_value = mock_response
                summarizer.client = mock_client

                content_data = self.create_mock_content_data()
                summarizer.summarize(content_data, language='de')

                # Verify chat.completions.create was called
                mock_client.chat.completions.create.assert_called_once()

                # Verify the call included messages
                call_kwargs = mock_client.chat.completions.create.call_args.kwargs
                assert 'messages' in call_kwargs
                assert 'model' in call_kwargs
                assert call_kwargs['model'] == 'test-model'

    def test_fetch_available_models_success(self):
        """Test fetching available models from LMStudio."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': [
                    {'id': 'model-a'},
                    {'id': 'model-b'},
                    {'id': 'model-c'}
                ]
            }

            summarizer = LMStudioProvider(model='model-a')
            models = summarizer._fetch_available_models()

            assert 'model-a' in models
            assert 'model-b' in models
            assert 'model-c' in models

    def test_fetch_available_models_server_down(self):
        """Test fetch_available_models returns empty list when server is down."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError()

            summarizer = LMStudioProvider.__new__(LMStudioProvider)
            summarizer.base_url = 'http://localhost:1234/v1'
            summarizer.model = None
            summarizer.timeout = 300
            models = summarizer._fetch_available_models()

            assert models == []

    def test_list_models_class_method(self):
        """Test list_models class method fetches from server."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'data': [
                    {'id': 'model-1'},
                    {'id': 'model-2'}
                ]
            }

            models = LMStudioProvider.list_models()

            assert len(models) == 2
            assert models[0].id == 'model-1'
            assert models[0].provider == 'lmstudio'
            assert models[0].is_default is True  # First model is default
            assert models[1].is_default is False

    def test_list_models_empty_on_server_error(self):
        """Test list_models returns empty list on server error."""
        with patch('requests.get') as mock_get:
            import requests
            mock_get.side_effect = requests.ConnectionError()

            models = LMStudioProvider.list_models()

            assert models == []

    def test_config_schema(self):
        """Test get_config_schema returns correct schema."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            schema = summarizer.get_config_schema()

            assert schema.requires_api_key is False
            assert len(schema.fields) == 2

            # Check base_url field
            base_url_field = next(f for f in schema.fields if f.key == 'base_url')
            assert base_url_field.type == 'string'
            assert base_url_field.env_var == 'LMSTUDIO_BASE_URL'
            assert base_url_field.editable is True

            # Check model field
            model_field = next(f for f in schema.fields if f.key == 'model')
            assert model_field.type == 'select'
            assert model_field.options_from == 'models'

    def test_default_timeout(self):
        """Test default timeout is set correctly."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            assert summarizer.timeout == 300  # 5 minutes

    def test_custom_timeout_parameter(self):
        """Test custom timeout via parameter."""
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model', timeout=600)
            assert summarizer.timeout == 600

    def test_timeout_from_env_var(self, monkeypatch):
        """Test timeout from environment variable."""
        monkeypatch.setenv('PROVIDER_TIMEOUT_LMSTUDIO', '120')
        with patch('requests.get'):
            summarizer = LMStudioProvider(model='test-model')
            assert summarizer.timeout == 120

    def test_provider_description(self):
        """Test provider has a description."""
        assert LMStudioProvider.description == "Local LLM via LMStudio server"

    def test_truncates_long_content(self):
        """Test that very long content is truncated."""
        with patch('requests.get'):
            with patch.object(LMStudioProvider, '__init__', lambda self, **kwargs: None):
                summarizer = LMStudioProvider.__new__(LMStudioProvider)
                summarizer.model = 'test-model'
                summarizer.base_url = 'http://localhost:1234/v1'
                summarizer.timeout = 300

                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = 'Summary'
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50

                mock_client.chat.completions.create.return_value = mock_response
                summarizer.client = mock_client

                # Create content longer than MAX_CONTENT_CHARS (80000)
                long_content = 'x' * 100000
                content_data = self.create_mock_content_data(content=long_content)

                summarizer.summarize(content_data, language='en')

                # The call should succeed (truncation happens internally)
                mock_client.chat.completions.create.assert_called_once()
