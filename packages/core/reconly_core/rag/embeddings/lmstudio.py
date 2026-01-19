"""LMStudio embedding provider implementation.

Supports local embedding models via LMStudio's OpenAI-compatible API.
"""
import asyncio
import os
from typing import Optional

import requests
from openai import OpenAI

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)


# Model configurations with their dimensions
# LMStudio can run various embedding models with different dimensions
LMSTUDIO_EMBEDDING_MODELS = {
    'nomic-embed-text': {
        'name': 'Nomic Embed Text',
        'dimension': 768,
        'description': 'Efficient embedding model with good performance',
    },
    'bge-m3': {
        'name': 'BGE-M3',
        'dimension': 1024,
        'description': 'Multi-lingual embedding model, excellent for semantic search',
    },
    'text-embedding-3-small': {
        'name': 'Text Embedding 3 Small (Compatible)',
        'dimension': 1536,
        'description': 'OpenAI-compatible embedding model',
    },
    'all-minilm-l6-v2': {
        'name': 'All-MiniLM-L6-v2',
        'dimension': 384,
        'description': 'Lightweight, fast embedding model',
    },
    'mxbai-embed-large': {
        'name': 'MixedBread Embed Large',
        'dimension': 1024,
        'description': 'Large embedding model with high accuracy',
    },
}

# Default model if not specified
DEFAULT_LMSTUDIO_EMBEDDING_MODEL = 'nomic-embed-text'
DEFAULT_LMSTUDIO_BASE_URL = 'http://localhost:1234/v1'


class LMStudioEmbedding(EmbeddingProvider):
    """Generates embeddings using LMStudio's OpenAI-compatible API.

    LMStudio provides a local server with an OpenAI-compatible endpoint,
    allowing use of the OpenAI SDK with a custom base URL.

    Example:
        >>> provider = LMStudioEmbedding(model='nomic-embed-text')
        >>> embeddings = await provider.embed(['Hello world', 'Test text'])
        >>> print(len(embeddings[0]))  # 768
    """

    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used, kept for interface consistency
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        Initialize the LMStudio embedding provider.

        Args:
            api_key: Not used (LMStudio doesn't require API keys)
            model: Model name to use (e.g., 'nomic-embed-text', 'bge-m3')
            base_url: LMStudio server URL (default: http://localhost:1234/v1)
            timeout: Request timeout in seconds
        """
        super().__init__(api_key=None)
        self.base_url = base_url or os.getenv('LMSTUDIO_BASE_URL', DEFAULT_LMSTUDIO_BASE_URL)
        self.timeout = timeout
        self.model = model or os.getenv('LMSTUDIO_EMBEDDING_MODEL', DEFAULT_LMSTUDIO_EMBEDDING_MODEL)

        # Get dimension from model config or default to 1024
        model_config = LMSTUDIO_EMBEDDING_MODELS.get(self.model, {})
        self._dimension = model_config.get('dimension', 1024)

        # Initialize OpenAI client with custom base URL
        # LMStudio doesn't require an API key, but OpenAI SDK needs a non-empty value
        self.client = OpenAI(
            api_key="lm-studio",  # Dummy key - LMStudio ignores this
            base_url=self.base_url,
            timeout=self.timeout,
        )

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'lmstudio'

    def get_dimension(self) -> int:
        """Get embedding vector dimension."""
        return self._dimension

    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            'provider': 'lmstudio',
            'model': self.model,
            'dimension': self._dimension,
            'base_url': self.base_url,
            'local': True,
        }

    @classmethod
    def get_capabilities(cls) -> EmbeddingProviderCapabilities:
        """Get provider capabilities."""
        return EmbeddingProviderCapabilities(
            is_local=True,
            requires_api_key=False,
            supports_batch=True,
            max_batch_size=32,
            max_tokens_per_text=8192,
            dimension=1024,  # Default dimension
        )

    def is_available(self) -> bool:
        """Check if LMStudio server is available."""
        try:
            # LMStudio uses OpenAI-compatible /v1/models endpoint
            response = requests.get(f"{self.base_url}/models", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def validate_config(self) -> list[str]:
        """Validate provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("LMStudio base URL is required")

        if self.base_url and not self.base_url.startswith('http'):
            errors.append("LMStudio base URL must start with http:// or https://")

        # Check if server is reachable
        if not self.is_available():
            errors.append(
                f"LMStudio server is not reachable at {self.base_url}. "
                "Make sure LMStudio is running with a local server enabled."
            )

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for LMStudio embedding provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="base_url",
                    type="string",
                    label="Base URL",
                    description="LMStudio server URL",
                    default=DEFAULT_LMSTUDIO_BASE_URL,
                    env_var="LMSTUDIO_BASE_URL",
                    editable=True,
                    placeholder="http://localhost:1234/v1",
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Embedding Model",
                    description="Embedding model to use (e.g., nomic-embed-text, bge-m3)",
                    default=DEFAULT_LMSTUDIO_EMBEDDING_MODEL,
                    env_var="LMSTUDIO_EMBEDDING_MODEL",
                    editable=True,
                    placeholder="nomic-embed-text",
                ),
            ],
            requires_api_key=False,
        )

    def _fetch_available_models(self) -> list[str]:
        """Fetch list of available models from LMStudio server."""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=2)
            if response.status_code == 200:
                data = response.json()
                # LMStudio returns OpenAI-compatible model list
                return [m['id'] for m in data.get('data', [])]
        except Exception:
            pass
        return []

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> list[EmbeddingModelInfo]:
        """List available embedding models."""
        models = []
        for model_id, config in LMSTUDIO_EMBEDDING_MODELS.items():
            models.append(EmbeddingModelInfo(
                id=model_id,
                name=config['name'],
                provider='lmstudio',
                dimension=config['dimension'],
                is_default=(model_id == DEFAULT_LMSTUDIO_EMBEDDING_MODEL),
            ))
        return models

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts using LMStudio.

        LMStudio's OpenAI-compatible API supports batch embedding,
        so we send all texts in a single request for efficiency.

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

        # LMStudio supports batch embedding via OpenAI-compatible API
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_batch_sync, texts)

    def _embed_batch_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous batch embedding using OpenAI SDK."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )

            # Extract embeddings in order
            embeddings: list[list[float]] = [[] for _ in range(len(texts))]
            for item in response.data:
                embeddings[item.index] = item.embedding

            # Update dimension from actual response if available
            if embeddings and embeddings[0]:
                actual_dimension = len(embeddings[0])
                if actual_dimension != self._dimension:
                    # Update internal dimension to match actual model output
                    self._dimension = actual_dimension

            return embeddings

        except Exception as e:
            error_msg = str(e)

            if 'connection' in error_msg.lower() or 'refused' in error_msg.lower():
                raise RuntimeError(
                    f"Could not connect to LMStudio server at {self.base_url}. "
                    "Make sure LMStudio is running with a local server enabled."
                )
            elif 'model' in error_msg.lower() and 'not found' in error_msg.lower():
                raise RuntimeError(
                    f"Model '{self.model}' not found in LMStudio. "
                    "Make sure an embedding model is loaded in LMStudio."
                )
            else:
                raise RuntimeError(
                    f"Failed to generate embeddings with LMStudio: {error_msg}"
                )
