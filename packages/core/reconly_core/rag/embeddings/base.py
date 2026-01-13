"""Base embedding provider interface.

This module defines the abstract base class for all embedding providers.
Follows the same pattern as summarizers for consistency.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from reconly_core.config_types import ProviderConfigSchema


@dataclass
class EmbeddingProviderCapabilities:
    """Capabilities of an embedding provider.

    Attributes:
        is_local: Whether provider runs locally (no API calls)
        requires_api_key: Whether provider requires an API key
        supports_batch: Whether provider supports batch embedding
        max_batch_size: Maximum texts per batch request
        max_tokens_per_text: Maximum tokens per individual text
        dimension: Output embedding dimension
    """
    is_local: bool = False
    requires_api_key: bool = True
    supports_batch: bool = True
    max_batch_size: int = 32
    max_tokens_per_text: int = 512
    dimension: int = 1024


@dataclass
class EmbeddingModelInfo:
    """Information about an embedding model.

    Attributes:
        id: Model identifier (e.g., 'bge-m3', 'text-embedding-3-small')
        name: Human-readable name
        provider: Provider name (e.g., 'ollama', 'openai')
        dimension: Embedding vector dimension
        is_default: Whether this is the default model for the provider
    """
    id: str
    name: str
    provider: str
    dimension: int
    is_default: bool = False


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    Subclasses must implement all abstract methods to provide embedding
    functionality using different providers (Ollama, OpenAI, HuggingFace).

    Example:
        >>> class OllamaEmbedding(EmbeddingProvider):
        ...     async def embed(self, texts):
        ...         # implementation
        ...     def get_dimension(self):
        ...         return 1024
        ...     def get_provider_name(self):
        ...         return "ollama"
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the embedding provider.

        Args:
            api_key: API key for the service (if required)
        """
        self.api_key = api_key

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors, one per input text.
            Each vector is a list of floats with length == get_dimension()

        Raises:
            ValueError: If texts is empty
            RuntimeError: If embedding generation fails
        """
        pass

    async def embed_single(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Convenience method that wraps embed() for single texts.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self.embed([text])
        return embeddings[0]

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the embedding vector dimension for this provider/model.

        Returns:
            Integer dimension of output vectors (e.g., 1024, 1536, 3072)
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the name of the provider.

        Returns:
            Provider name (e.g., 'ollama', 'openai', 'huggingface')
        """
        pass

    def get_model_info(self) -> dict:
        """
        Get information about the model being used.

        Returns:
            Dictionary with model information
        """
        return {
            'provider': self.get_provider_name(),
            'model': 'unknown',
            'dimension': self.get_dimension()
        }

    @classmethod
    @abstractmethod
    def get_capabilities(cls) -> EmbeddingProviderCapabilities:
        """
        Get provider capabilities for runtime feature discovery.

        Returns:
            EmbeddingProviderCapabilities instance describing this provider
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is currently available.

        Returns:
            True if provider can process requests, False otherwise
        """
        pass

    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        Validate provider configuration and return list of errors.

        Returns:
            List of error strings (empty list if configuration is valid)
        """
        pass

    def get_config_schema(self) -> ProviderConfigSchema:
        """
        Get the configuration schema for this provider.

        Returns:
            ProviderConfigSchema with field definitions
        """
        return ProviderConfigSchema(fields=[], requires_api_key=False)

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[EmbeddingModelInfo]:
        """
        List available models for this provider.

        Args:
            api_key: Optional API key for providers that require auth

        Returns:
            List of EmbeddingModelInfo objects for available models
        """
        return []
