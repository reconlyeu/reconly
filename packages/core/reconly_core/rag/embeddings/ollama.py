"""Ollama embedding provider implementation.

Supports local embedding models via Ollama server.
"""
import asyncio
import os
from typing import List, Optional

import requests

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)


# Model configurations with their dimensions
OLLAMA_EMBEDDING_MODELS = {
    'bge-m3': {
        'name': 'BGE-M3',
        'dimension': 1024,
        'description': 'Multi-lingual embedding model, excellent for semantic search',
    },
    'nomic-embed-text': {
        'name': 'Nomic Embed Text',
        'dimension': 768,
        'description': 'Efficient embedding model with good performance',
    },
    'mxbai-embed-large': {
        'name': 'MixedBread Embed Large',
        'dimension': 1024,
        'description': 'Large embedding model with high accuracy',
    },
    'all-minilm': {
        'name': 'All-MiniLM',
        'dimension': 384,
        'description': 'Lightweight, fast embedding model',
    },
    'snowflake-arctic-embed': {
        'name': 'Snowflake Arctic Embed',
        'dimension': 1024,
        'description': 'High-quality embedding model from Snowflake',
    },
}

# Default model if not specified
DEFAULT_OLLAMA_EMBEDDING_MODEL = 'bge-m3'


class OllamaEmbedding(EmbeddingProvider):
    """Generates embeddings using local Ollama server.

    Supports models like bge-m3 (1024 dims), nomic-embed-text (768 dims).
    Ollama must be running locally with the embedding model pulled.

    Example:
        >>> provider = OllamaEmbedding(model='bge-m3')
        >>> embeddings = await provider.embed(['Hello world', 'Test text'])
        >>> print(len(embeddings[0]))  # 1024
    """

    def __init__(
        self,
        api_key: Optional[str] = None,  # Not used, kept for interface consistency
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 120,
    ):
        """
        Initialize the Ollama embedding provider.

        Args:
            api_key: Not used (Ollama doesn't require API keys)
            model: Model name to use (e.g., 'bge-m3', 'nomic-embed-text')
            base_url: Ollama server URL (default: http://localhost:11434)
            timeout: Request timeout in seconds
        """
        super().__init__(api_key=None)
        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.timeout = timeout
        self.model = model or os.getenv('EMBEDDING_MODEL', DEFAULT_OLLAMA_EMBEDDING_MODEL)

        # Get dimension from model config or default
        model_config = OLLAMA_EMBEDDING_MODELS.get(self.model, {})
        self._dimension = model_config.get('dimension', 1024)

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'ollama'

    def get_dimension(self) -> int:
        """Get embedding vector dimension."""
        return self._dimension

    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            'provider': 'ollama',
            'model': self.model,
            'dimension': self._dimension,
            'base_url': self.base_url,
            'local': True
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
            dimension=1024,  # Default for bge-m3
        )

    def is_available(self) -> bool:
        """Check if Ollama server is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("Ollama base URL is required")

        if self.base_url and not self.base_url.startswith('http'):
            errors.append("Ollama base URL must start with http:// or https://")

        # Check if server is reachable
        if not self.is_available():
            errors.append(
                f"Ollama server is not reachable at {self.base_url}. "
                "Make sure Ollama is running."
            )

        # Check if embedding model is available
        available_models = self._fetch_available_models()
        if available_models and self.model not in available_models:
            errors.append(
                f"Embedding model '{self.model}' is not available. "
                f"Run 'ollama pull {self.model}' to download it."
            )

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for Ollama embedding provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="base_url",
                    type="string",
                    label="Base URL",
                    description="Ollama server URL",
                    default="http://localhost:11434",
                    env_var="OLLAMA_BASE_URL",
                    editable=True,
                    placeholder="http://localhost:11434",
                ),
                ConfigField(
                    key="model",
                    type="string",
                    label="Embedding Model",
                    description="Embedding model to use (e.g., bge-m3, nomic-embed-text)",
                    default=DEFAULT_OLLAMA_EMBEDDING_MODEL,
                    env_var="EMBEDDING_MODEL",
                    editable=True,
                    placeholder="bge-m3",
                ),
            ],
            requires_api_key=False,
        )

    def _fetch_available_models(self) -> List[str]:
        """Fetch list of available models from Ollama server."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return [m['name'] for m in data.get('models', [])]
        except Exception:
            pass
        return []

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[EmbeddingModelInfo]:
        """List available embedding models."""
        models = []
        for model_id, config in OLLAMA_EMBEDDING_MODELS.items():
            models.append(EmbeddingModelInfo(
                id=model_id,
                name=config['name'],
                provider='ollama',
                dimension=config['dimension'],
                is_default=(model_id == DEFAULT_OLLAMA_EMBEDDING_MODEL),
            ))
        return models

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using Ollama.

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

        embeddings = []

        # Ollama's embedding API handles one text at a time
        # We process sequentially to avoid overwhelming the server
        for text in texts:
            embedding = await self._embed_single(text)
            embeddings.append(embedding)

        return embeddings

    async def _embed_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        # Run synchronous request in thread pool to make it async
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_sync, text)

    def _embed_sync(self, text: str) -> List[float]:
        """Synchronous embedding for a single text."""
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text,
                },
                timeout=self.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Ollama API error {response.status_code}: {response.text}"
                )

            result = response.json()
            embedding = result.get('embedding')

            if not embedding:
                raise RuntimeError("Ollama returned empty embedding")

            return embedding

        except requests.Timeout:
            raise RuntimeError(
                f"Ollama embedding request timed out after {self.timeout}s"
            )
        except requests.ConnectionError:
            raise RuntimeError(
                f"Could not connect to Ollama server at {self.base_url}. "
                "Make sure Ollama is running."
            )

