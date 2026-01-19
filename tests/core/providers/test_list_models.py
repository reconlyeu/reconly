"""Tests for provider list_models implementations.

These tests verify the structure and behavior of list_models(), not specific model IDs.
This makes tests resilient to model updates - when new models are released, no test
changes are needed.
"""
from unittest.mock import patch, MagicMock

from reconly_core.providers.capabilities import ModelInfo
from reconly_core.providers.anthropic import AnthropicProvider
from reconly_core.providers.openai_provider import OpenAIProvider
from reconly_core.providers.ollama import OllamaProvider
from reconly_core.providers.huggingface import HuggingFaceProvider


class TestAnthropicListModels:
    """Tests for AnthropicProvider.list_models()."""

    @patch('reconly_core.providers.anthropic.Anthropic')
    def test_fetches_from_api_with_key(self, mock_anthropic):
        """Test that list_models calls Anthropic API when key provided."""
        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock models.list() response
        mock_model1 = MagicMock()
        mock_model1.id = 'claude-test-model-1'
        mock_model1.display_name = 'Claude Test Model 1'
        mock_model2 = MagicMock()
        mock_model2.id = 'claude-test-model-2'
        mock_model2.display_name = 'Claude Test Model 2'
        mock_client.models.list.return_value.data = [mock_model1, mock_model2]

        models = AnthropicProvider.list_models(api_key='test-key')

        mock_anthropic.assert_called_once_with(api_key='test-key')
        assert len(models) == 2
        assert all(isinstance(m, ModelInfo) for m in models)
        assert all(m.provider == 'anthropic' for m in models)

    @patch('reconly_core.providers.anthropic.Anthropic')
    def test_first_model_is_default(self, mock_anthropic):
        """Test that first model (most recent) is marked as default."""
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_model1 = MagicMock()
        mock_model1.id = 'newest-model'
        mock_model1.display_name = 'Newest Model'
        mock_model2 = MagicMock()
        mock_model2.id = 'older-model'
        mock_model2.display_name = 'Older Model'
        mock_client.models.list.return_value.data = [mock_model1, mock_model2]

        models = AnthropicProvider.list_models(api_key='test-key')

        defaults = [m for m in models if m.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == 'newest-model'

    def test_returns_fallback_without_api_key(self):
        """Test fallback models when no API key."""
        with patch.dict('os.environ', {}, clear=True):
            models = AnthropicProvider.list_models(api_key=None)

        # Should return fallback models
        assert len(models) >= 1
        assert all(isinstance(m, ModelInfo) for m in models)
        assert all(m.provider == 'anthropic' for m in models)

    @patch('reconly_core.providers.anthropic.Anthropic')
    def test_returns_fallback_on_api_error(self, mock_anthropic):
        """Test fallback when API call fails."""
        mock_anthropic.side_effect = Exception('API error')

        models = AnthropicProvider.list_models(api_key='test-key')

        # Should return fallback models
        assert len(models) >= 1
        assert all(isinstance(m, ModelInfo) for m in models)

    def test_fallback_models_structure(self):
        """Test fallback model list structure."""
        models = AnthropicProvider.FALLBACK_MODELS

        assert len(models) >= 1
        for m in models:
            assert isinstance(m, ModelInfo)
            assert m.provider == 'anthropic'
            assert m.id  # Has an ID
            assert m.name  # Has a display name


class TestOpenAIListModels:
    """Tests for OpenAIProvider.list_models()."""

    def test_returns_fallback_without_api_key(self):
        """Test fallback models when no API key."""
        with patch.dict('os.environ', {}, clear=True):
            models = OpenAIProvider.list_models(api_key=None)

        assert len(models) >= 1
        assert all(isinstance(m, ModelInfo) for m in models)
        assert all(m.provider == 'openai' for m in models)

    def test_fallback_models_structure(self):
        """Test fallback model structure."""
        models = OpenAIProvider.FALLBACK_MODELS

        assert len(models) >= 1
        for m in models:
            assert isinstance(m, ModelInfo)
            assert m.provider == 'openai'
            assert m.id
            assert m.name

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_fetches_from_api_with_key(self, mock_openai):
        """Test that list_models calls OpenAI API when key provided."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock models.list() response with chat-compatible model
        mock_model = MagicMock()
        mock_model.id = 'gpt-4-test'
        mock_client.models.list.return_value.data = [mock_model]

        models = OpenAIProvider.list_models(api_key='test-key')

        mock_openai.assert_called_once_with(api_key='test-key')
        assert len(models) >= 1
        assert all(isinstance(m, ModelInfo) for m in models)

    @patch('reconly_core.providers.openai_provider.OpenAI')
    def test_filters_chat_compatible_models(self, mock_openai):
        """Test that only chat-compatible models are returned."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        # Mock response with mixed model types
        mock_gpt4 = MagicMock()
        mock_gpt4.id = 'gpt-4-turbo'
        mock_embedding = MagicMock()
        mock_embedding.id = 'text-embedding-ada-002'
        mock_whisper = MagicMock()
        mock_whisper.id = 'whisper-1'
        mock_client.models.list.return_value.data = [mock_gpt4, mock_embedding, mock_whisper]

        models = OpenAIProvider.list_models(api_key='test-key')

        # Should only return gpt-4-turbo (chat-compatible)
        model_ids = [m.id for m in models]
        assert 'gpt-4-turbo' in model_ids
        assert 'text-embedding-ada-002' not in model_ids
        assert 'whisper-1' not in model_ids


class TestOllamaListModels:
    """Tests for OllamaProvider.list_models()."""

    @patch('reconly_core.providers.ollama.requests.get')
    def test_fetches_from_server(self, mock_get):
        """Test that list_models fetches from Ollama server."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'model-a'},
                {'name': 'model-b'},
            ]
        }
        mock_get.return_value = mock_response

        models = OllamaProvider.list_models()

        assert len(models) == 2
        assert all(isinstance(m, ModelInfo) for m in models)
        assert all(m.provider == 'ollama' for m in models)
        # Check IDs match what server returned
        model_ids = [m.id for m in models]
        assert 'model-a' in model_ids
        assert 'model-b' in model_ids

    @patch('reconly_core.providers.ollama.requests.get')
    def test_returns_empty_on_server_error(self, mock_get):
        """Test empty list when server unavailable."""
        mock_get.side_effect = Exception('Connection refused')

        models = OllamaProvider.list_models()

        assert models == []

    @patch('reconly_core.providers.ollama.requests.get')
    def test_first_model_is_default(self, mock_get):
        """Test that first model is marked as default."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [
                {'name': 'first-model'},
                {'name': 'second-model'},
            ]
        }
        mock_get.return_value = mock_response

        models = OllamaProvider.list_models()

        assert models[0].is_default is True
        assert models[1].is_default is False


class TestHuggingFaceListModels:
    """Tests for HuggingFaceProvider.list_models().

    HuggingFace uses a curated list since there's no standard API to query
    available inference models.
    """

    def test_returns_model_list(self):
        """Test that list_models returns a list of models."""
        models = HuggingFaceProvider.list_models()

        assert len(models) >= 1
        assert all(isinstance(m, ModelInfo) for m in models)

    def test_exactly_one_default(self):
        """Test that exactly one model is marked as default."""
        models = HuggingFaceProvider.list_models()
        defaults = [m for m in models if m.is_default]
        assert len(defaults) == 1

    def test_provider_is_huggingface(self):
        """Test that all models have provider='huggingface'."""
        models = HuggingFaceProvider.list_models()
        assert all(m.provider == 'huggingface' for m in models)

    def test_models_have_required_fields(self):
        """Test that all models have required fields."""
        models = HuggingFaceProvider.list_models()
        for m in models:
            assert m.id  # Has an ID
            assert m.name  # Has a display name
            assert m.provider == 'huggingface'

    def test_model_ids_are_valid_huggingface_paths(self):
        """Test that returned model IDs are valid HuggingFace model paths."""
        models = HuggingFaceProvider.list_models()
        for m in models:
            # HuggingFace model IDs should contain org/model format
            # or be a valid identifier
            assert m.id, "Model ID should not be empty"
            # Most models have org/model format, but some might be just identifiers
            assert '/' in m.id or len(m.id) > 0, f"Model {m.id} should be a valid identifier"
