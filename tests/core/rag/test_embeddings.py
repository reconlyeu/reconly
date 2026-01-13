"""Tests for embedding providers."""
import pytest
from unittest.mock import patch, Mock, AsyncMock
import requests

from reconly_core.rag.embeddings import (
    get_embedding_provider,
    list_embedding_providers,
    list_embedding_models,
    get_embedding_dimension,
)
from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)
from reconly_core.rag.embeddings.ollama import OllamaEmbedding


class TestEmbeddingProviderFactory:
    """Tests for embedding provider factory functions."""

    def test_list_embedding_providers(self):
        """Test listing available providers."""
        providers = list_embedding_providers()

        assert isinstance(providers, list)
        assert 'ollama' in providers
        assert 'openai' in providers
        assert 'huggingface' in providers

    def test_list_embedding_models_all(self):
        """Test listing models for all providers."""
        models = list_embedding_models()

        assert isinstance(models, dict)
        assert 'ollama' in models
        assert 'openai' in models
        assert 'huggingface' in models

        # Check model structure
        for provider, model_list in models.items():
            assert isinstance(model_list, list)
            for model in model_list:
                assert isinstance(model, EmbeddingModelInfo)
                assert model.id
                assert model.name
                assert model.provider == provider
                assert model.dimension > 0

    def test_list_embedding_models_single_provider(self):
        """Test listing models for a specific provider."""
        models = list_embedding_models('ollama')

        assert 'ollama' in models
        assert len(models) == 1
        assert len(models['ollama']) > 0

    def test_get_embedding_dimension_ollama(self):
        """Test getting dimension for Ollama models."""
        assert get_embedding_dimension('ollama', 'bge-m3') == 1024
        assert get_embedding_dimension('ollama', 'nomic-embed-text') == 768

    def test_get_embedding_dimension_openai(self):
        """Test getting dimension for OpenAI models."""
        assert get_embedding_dimension('openai', 'text-embedding-3-small') == 1536
        assert get_embedding_dimension('openai', 'text-embedding-3-large') == 3072

    def test_get_embedding_dimension_default(self):
        """Test default dimension for unknown models."""
        dim = get_embedding_dimension('ollama', 'unknown-model')
        assert dim == 1024  # Default

    @patch.dict('os.environ', {'EMBEDDING_PROVIDER': 'ollama'})
    def test_get_embedding_provider_from_env(self):
        """Test provider selection from environment variable."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'models': []}

            provider = get_embedding_provider()
            assert provider.get_provider_name() == 'ollama'

    def test_get_embedding_provider_unknown(self):
        """Test error for unknown provider."""
        with pytest.raises(ValueError) as exc_info:
            get_embedding_provider('unknown_provider')

        assert 'Unknown embedding provider' in str(exc_info.value)

    def test_get_embedding_provider_ollama_default(self):
        """Test that Ollama is the default provider."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'models': []}

            provider = get_embedding_provider()
            assert provider.get_provider_name() == 'ollama'


class TestOllamaEmbedding:
    """Tests for OllamaEmbedding provider."""

    @pytest.fixture
    def provider(self):
        """Return configured Ollama embedding provider."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [{'name': 'bge-m3'}]
            }
            return OllamaEmbedding(model='bge-m3')

    def test_initialization_default(self):
        """Test default initialization."""
        with patch('requests.get'):
            provider = OllamaEmbedding()
            assert provider.base_url == 'http://localhost:11434'
            assert provider.model in ['bge-m3', None] or 'bge' in provider.model

    def test_initialization_custom_model(self):
        """Test initialization with custom model."""
        with patch('requests.get'):
            provider = OllamaEmbedding(model='nomic-embed-text')
            assert provider.model == 'nomic-embed-text'
            assert provider.get_dimension() == 768

    def test_initialization_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch('requests.get'):
            provider = OllamaEmbedding(base_url='http://192.168.1.100:11434')
            assert provider.base_url == 'http://192.168.1.100:11434'

    def test_get_provider_name(self, provider):
        """Test provider name."""
        assert provider.get_provider_name() == 'ollama'

    def test_get_dimension(self, provider):
        """Test dimension for bge-m3."""
        assert provider.get_dimension() == 1024

    def test_get_model_info(self, provider):
        """Test model info structure."""
        info = provider.get_model_info()

        assert info['provider'] == 'ollama'
        assert info['model'] == 'bge-m3'
        assert info['dimension'] == 1024
        assert info['local'] is True

    def test_get_capabilities(self):
        """Test provider capabilities."""
        caps = OllamaEmbedding.get_capabilities()

        assert isinstance(caps, EmbeddingProviderCapabilities)
        assert caps.is_local is True
        assert caps.requires_api_key is False
        assert caps.supports_batch is True

    def test_is_available_server_running(self):
        """Test is_available when server is running."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200

            provider = OllamaEmbedding()
            assert provider.is_available() is True

    def test_is_available_server_not_running(self):
        """Test is_available when server is not running."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError()

            provider = OllamaEmbedding()
            assert provider.is_available() is False

    def test_validate_config_success(self):
        """Test validate_config with valid config."""
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                'models': [{'name': 'bge-m3'}]
            }

            provider = OllamaEmbedding(model='bge-m3')
            errors = provider.validate_config()

            assert isinstance(errors, list)
            assert len(errors) == 0

    def test_validate_config_server_unreachable(self):
        """Test validate_config when server is unreachable."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.ConnectionError()

            provider = OllamaEmbedding()
            errors = provider.validate_config()

            assert len(errors) > 0
            assert any('not reachable' in e.lower() for e in errors)

    def test_list_models(self):
        """Test listing available models."""
        models = OllamaEmbedding.list_models()

        assert isinstance(models, list)
        assert len(models) > 0

        model_ids = [m.id for m in models]
        assert 'bge-m3' in model_ids

    @pytest.mark.asyncio
    async def test_embed_single_text(self):
        """Test embedding a single text."""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'models': []}

            # Mock embedding response
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'embedding': [0.1] * 1024  # Mock 1024-dim embedding
            }

            provider = OllamaEmbedding(model='bge-m3')
            embedding = await provider.embed_single("Test text")

            assert isinstance(embedding, list)
            assert len(embedding) == 1024

    @pytest.mark.asyncio
    async def test_embed_multiple_texts(self):
        """Test embedding multiple texts."""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'models': []}

            # Mock embedding response
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                'embedding': [0.1] * 1024
            }

            provider = OllamaEmbedding(model='bge-m3')
            embeddings = await provider.embed(["Text 1", "Text 2", "Text 3"])

            assert isinstance(embeddings, list)
            assert len(embeddings) == 3
            for emb in embeddings:
                assert len(emb) == 1024

    @pytest.mark.asyncio
    async def test_embed_empty_list_raises(self):
        """Test that embedding empty list raises error."""
        with patch('requests.get'):
            provider = OllamaEmbedding()

            with pytest.raises(ValueError):
                await provider.embed([])

    @pytest.mark.asyncio
    async def test_embed_connection_error(self):
        """Test handling of connection errors."""
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'models': []}
            mock_post.side_effect = requests.ConnectionError()

            provider = OllamaEmbedding()

            with pytest.raises(RuntimeError) as exc_info:
                await provider.embed(["Test"])

            assert 'Could not connect' in str(exc_info.value)


class TestEmbeddingProviderBase:
    """Tests for EmbeddingProvider base class."""

    def test_embedding_provider_is_abstract(self):
        """Test that EmbeddingProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            EmbeddingProvider()

    def test_embedding_model_info_structure(self):
        """Test EmbeddingModelInfo dataclass."""
        info = EmbeddingModelInfo(
            id='test-model',
            name='Test Model',
            provider='test',
            dimension=768,
            is_default=True,
        )

        assert info.id == 'test-model'
        assert info.name == 'Test Model'
        assert info.provider == 'test'
        assert info.dimension == 768
        assert info.is_default is True

    def test_embedding_capabilities_structure(self):
        """Test EmbeddingProviderCapabilities dataclass."""
        caps = EmbeddingProviderCapabilities(
            is_local=True,
            requires_api_key=False,
            supports_batch=True,
            max_batch_size=32,
            max_tokens_per_text=512,
            dimension=1024,
        )

        assert caps.is_local is True
        assert caps.requires_api_key is False
        assert caps.supports_batch is True
        assert caps.max_batch_size == 32
        assert caps.max_tokens_per_text == 512
        assert caps.dimension == 1024
