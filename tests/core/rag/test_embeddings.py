"""Tests for embedding providers."""
import pytest
from unittest.mock import patch
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


class TestEmbeddingProviderRegistry:
    """Tests for embedding provider registry and metadata."""

    def test_get_metadata_ollama(self):
        """Test metadata retrieval for Ollama provider."""
        from reconly_core.rag.embeddings import OllamaEmbedding
        from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata

        metadata = OllamaEmbedding.get_metadata()

        assert isinstance(metadata, EmbeddingProviderMetadata)
        assert metadata.name == 'ollama'
        assert metadata.display_name == 'Ollama'
        assert metadata.is_local is True
        assert metadata.requires_api_key is False
        assert metadata.supports_base_url is True
        assert metadata.model_param_name == 'model'
        assert metadata.default_model == 'bge-m3'

    def test_get_metadata_openai(self):
        """Test metadata retrieval for OpenAI provider."""
        from reconly_core.rag.embeddings import OpenAIEmbedding
        from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata

        metadata = OpenAIEmbedding.get_metadata()

        assert isinstance(metadata, EmbeddingProviderMetadata)
        assert metadata.name == 'openai'
        assert metadata.display_name == 'OpenAI'
        assert metadata.is_local is False
        assert metadata.requires_api_key is True
        assert metadata.supports_base_url is True
        assert metadata.model_param_name == 'model'
        assert metadata.default_model == 'text-embedding-3-small'

    def test_get_metadata_huggingface(self):
        """Test metadata retrieval for HuggingFace provider."""
        from reconly_core.rag.embeddings import HuggingFaceEmbedding
        from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata

        metadata = HuggingFaceEmbedding.get_metadata()

        assert isinstance(metadata, EmbeddingProviderMetadata)
        assert metadata.name == 'huggingface'
        assert metadata.display_name == 'HuggingFace'
        assert metadata.is_local is False
        assert metadata.requires_api_key is True
        assert metadata.supports_base_url is False
        assert metadata.model_param_name == 'model_id'
        assert metadata.default_model == 'BAAI/bge-m3'

    def test_get_metadata_lmstudio(self):
        """Test metadata retrieval for LMStudio provider."""
        from reconly_core.rag.embeddings import LMStudioEmbedding
        from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata

        metadata = LMStudioEmbedding.get_metadata()

        assert isinstance(metadata, EmbeddingProviderMetadata)
        assert metadata.name == 'lmstudio'
        assert metadata.display_name == 'LM Studio'
        assert metadata.is_local is True
        assert metadata.requires_api_key is False
        assert metadata.supports_base_url is True
        assert metadata.model_param_name == 'model'
        assert metadata.default_model == 'nomic-embed-text'

    def test_list_embedding_provider_metadata(self):
        """Test listing metadata for all providers."""
        from reconly_core.rag.embeddings import list_embedding_provider_metadata

        metadata_list = list_embedding_provider_metadata()

        assert isinstance(metadata_list, list)
        assert len(metadata_list) >= 4  # At least 4 core providers

        # Check all metadata are dicts
        for metadata in metadata_list:
            assert isinstance(metadata, dict)
            assert 'name' in metadata
            assert 'display_name' in metadata
            assert 'description' in metadata
            assert 'is_local' in metadata
            assert 'requires_api_key' in metadata

        # Verify core providers are present
        names = [m['name'] for m in metadata_list]
        assert 'ollama' in names
        assert 'openai' in names
        assert 'huggingface' in names
        assert 'lmstudio' in names

    def test_get_embedding_provider_class(self):
        """Test retrieving provider classes by name."""
        from reconly_core.rag.embeddings import (
            get_embedding_provider_class,
            OllamaEmbedding,
            OpenAIEmbedding,
            HuggingFaceEmbedding,
            LMStudioEmbedding,
        )

        # Test retrieval of each core provider
        assert get_embedding_provider_class('ollama') is OllamaEmbedding
        assert get_embedding_provider_class('openai') is OpenAIEmbedding
        assert get_embedding_provider_class('huggingface') is HuggingFaceEmbedding
        assert get_embedding_provider_class('lmstudio') is LMStudioEmbedding

        # Test non-existent provider
        assert get_embedding_provider_class('nonexistent') is None

    def test_register_embedding_provider_decorator(self):
        """Test the register_embedding_provider decorator."""
        from reconly_core.rag.embeddings import (
            register_embedding_provider,
            get_embedding_provider_class,
            list_embedding_providers,
        )
        from reconly_core.rag.embeddings.base import EmbeddingProvider
        from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata

        # Create a test provider class
        @register_embedding_provider('test_provider')
        class TestEmbeddingProvider(EmbeddingProvider):
            @classmethod
            def get_metadata(cls):
                return EmbeddingProviderMetadata(
                    name='test_provider',
                    display_name='Test Provider',
                    description='A test provider',
                )

            @classmethod
            def get_capabilities(cls):
                from reconly_core.rag.embeddings.base import EmbeddingProviderCapabilities
                return EmbeddingProviderCapabilities(
                    is_local=True,
                    requires_api_key=False,
                    supports_batch=False,
                )

            @classmethod
            def list_models(cls):
                from reconly_core.rag.embeddings.base import EmbeddingModelInfo
                return [
                    EmbeddingModelInfo(
                        id='test-model',
                        name='Test Model',
                        provider='test_provider',
                        dimension=768,
                    )
                ]

            def get_provider_name(self):
                return 'test_provider'

            def get_dimension(self):
                return 768

            def get_model_info(self):
                return {
                    'provider': 'test_provider',
                    'model': 'test-model',
                    'dimension': 768,
                    'local': True,
                }

            def is_available(self):
                return True

            def validate_config(self):
                return []

            async def embed(self, texts):
                return [[0.1] * 768 for _ in texts]

        # Verify registration
        assert 'test_provider' in list_embedding_providers()
        assert get_embedding_provider_class('test_provider') is TestEmbeddingProvider

    def test_dynamic_initialization_via_get_embedding_provider(self):
        """Test dynamic provider instantiation via get_embedding_provider."""
        from reconly_core.rag.embeddings import get_embedding_provider

        # Test Ollama provider
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {'models': []}

            provider = get_embedding_provider('ollama', model='bge-m3')
            assert provider.get_provider_name() == 'ollama'
            assert provider.model == 'bge-m3'

        # Test OpenAI provider
        provider = get_embedding_provider('openai', model='text-embedding-3-small', api_key='test-key')
        assert provider.get_provider_name() == 'openai'
        assert provider.model == 'text-embedding-3-small'

        # Test HuggingFace provider
        provider = get_embedding_provider('huggingface', model='BAAI/bge-m3', api_key='test-key')
        assert provider.get_provider_name() == 'huggingface'
        assert provider.model_id == 'BAAI/bge-m3'

        # Test LMStudio provider
        provider = get_embedding_provider('lmstudio', model='nomic-embed-text')
        assert provider.get_provider_name() == 'lmstudio'
        assert provider.model == 'nomic-embed-text'

    def test_metadata_to_dict_conversion(self):
        """Test EmbeddingProviderMetadata to_dict conversion."""
        from reconly_core.rag.embeddings import OllamaEmbedding

        metadata = OllamaEmbedding.get_metadata()
        metadata_dict = metadata.to_dict()

        assert isinstance(metadata_dict, dict)
        assert metadata_dict['name'] == 'ollama'
        assert metadata_dict['display_name'] == 'Ollama'
        assert metadata_dict['is_local'] is True
        assert metadata_dict['requires_api_key'] is False
        assert metadata_dict['supports_base_url'] is True
        assert metadata_dict['model_param_name'] == 'model'
        assert metadata_dict['default_model'] == 'bge-m3'
        assert 'description' in metadata_dict
        assert 'icon' in metadata_dict
