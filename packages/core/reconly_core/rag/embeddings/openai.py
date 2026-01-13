"""OpenAI embedding provider implementation.

Supports OpenAI's text-embedding models via their API.
"""
import asyncio
import os
from typing import List, Optional

from openai import OpenAI

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)


# OpenAI embedding model configurations
OPENAI_EMBEDDING_MODELS = {
    'text-embedding-3-small': {
        'name': 'Text Embedding 3 Small',
        'dimension': 1536,
        'description': 'Most cost-effective embedding model',
        'max_tokens': 8191,
    },
    'text-embedding-3-large': {
        'name': 'Text Embedding 3 Large',
        'dimension': 3072,
        'description': 'Highest quality embedding model',
        'max_tokens': 8191,
    },
    'text-embedding-ada-002': {
        'name': 'Ada 002 (Legacy)',
        'dimension': 1536,
        'description': 'Legacy embedding model',
        'max_tokens': 8191,
    },
}

# Default model
DEFAULT_OPENAI_EMBEDDING_MODEL = 'text-embedding-3-small'


class OpenAIEmbedding(EmbeddingProvider):
    """Generates embeddings using OpenAI's embedding API.

    Supports text-embedding-3-small (1536 dims) and text-embedding-3-large (3072 dims).

    Example:
        >>> provider = OpenAIEmbedding(api_key='sk-...')
        >>> embeddings = await provider.embed(['Hello world', 'Test text'])
        >>> print(len(embeddings[0]))  # 1536
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize the OpenAI embedding provider.

        Args:
            api_key: OpenAI API key (if not provided, reads from OPENAI_API_KEY)
            model: Model to use (default: text-embedding-3-small)
            base_url: Base URL for OpenAI-compatible endpoints (optional)
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')

        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model = model or os.getenv('EMBEDDING_MODEL', DEFAULT_OPENAI_EMBEDDING_MODEL)
        self.base_url = base_url or os.getenv('OPENAI_BASE_URL')

        # Get dimension from model config
        model_config = OPENAI_EMBEDDING_MODELS.get(self.model, {})
        self._dimension = model_config.get('dimension', 1536)
        self._max_tokens = model_config.get('max_tokens', 8191)

        # Initialize OpenAI client
        if self.base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = OpenAI(api_key=self.api_key)

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'openai'

    def get_dimension(self) -> int:
        """Get embedding vector dimension."""
        return self._dimension

    def get_model_info(self) -> dict:
        """Get model information."""
        info = {
            'provider': 'openai',
            'model': self.model,
            'dimension': self._dimension,
        }
        if self.base_url:
            info['base_url'] = self.base_url
            info['compatible_endpoint'] = True
        return info

    @classmethod
    def get_capabilities(cls) -> EmbeddingProviderCapabilities:
        """Get provider capabilities."""
        return EmbeddingProviderCapabilities(
            is_local=False,
            requires_api_key=True,
            supports_batch=True,
            max_batch_size=2048,  # OpenAI supports large batches
            max_tokens_per_text=8191,
            dimension=1536,  # Default for text-embedding-3-small
        )

    def is_available(self) -> bool:
        """Check if provider is available (API key is set)."""
        return self.api_key is not None and len(self.api_key) > 0

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.api_key:
            errors.append(
                "OpenAI API key is required but not set. "
                "Set OPENAI_API_KEY environment variable."
            )

        if self.model not in OPENAI_EMBEDDING_MODELS:
            errors.append(
                f"Unknown embedding model '{self.model}'. "
                f"Available: {list(OPENAI_EMBEDDING_MODELS.keys())}"
            )

        if self.base_url and not self.base_url.startswith('http'):
            errors.append("Base URL must start with http:// or https://")

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for OpenAI embedding provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="OpenAI API key",
                    env_var="OPENAI_API_KEY",
                    editable=False,
                    secret=True,
                    required=True,
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Embedding Model",
                    description="Model to use (text-embedding-3-small or text-embedding-3-large)",
                    default=DEFAULT_OPENAI_EMBEDDING_MODEL,
                    env_var="EMBEDDING_MODEL",
                    editable=True,
                    placeholder="text-embedding-3-small",
                ),
            ],
            requires_api_key=True,
        )

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[EmbeddingModelInfo]:
        """List available embedding models."""
        models = []
        for model_id, config in OPENAI_EMBEDDING_MODELS.items():
            # Skip legacy models in list
            if 'Legacy' in config['name']:
                continue
            models.append(EmbeddingModelInfo(
                id=model_id,
                name=config['name'],
                provider='openai',
                dimension=config['dimension'],
                is_default=(model_id == DEFAULT_OPENAI_EMBEDDING_MODEL),
            ))
        return models

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using OpenAI.

        OpenAI's API supports batch embedding natively, so we send
        all texts in a single request for efficiency.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If texts is empty
            RuntimeError: If embedding generation fails
        """
        if not texts:
            raise ValueError("Cannot embed empty list of texts")

        # OpenAI supports batch embedding - send all at once
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_batch_sync, texts)

    def _embed_batch_sync(self, texts: List[str]) -> List[List[float]]:
        """Synchronous batch embedding."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )

            # Extract embeddings in order
            embeddings: list[list[float]] = [[] for _ in range(len(texts))]
            for item in response.data:
                embeddings[item.index] = item.embedding

            return embeddings

        except Exception as e:
            error_msg = str(e)

            if 'rate_limit' in error_msg.lower():
                raise RuntimeError(
                    f"OpenAI rate limit exceeded: {error_msg}. "
                    "Wait a moment and try again."
                )
            elif 'authentication' in error_msg.lower() or 'api_key' in error_msg.lower():
                raise RuntimeError(
                    f"OpenAI authentication failed: {error_msg}. "
                    "Check that your OPENAI_API_KEY is valid."
                )
            else:
                raise RuntimeError(
                    f"Failed to generate embeddings with OpenAI: {error_msg}"
                )

