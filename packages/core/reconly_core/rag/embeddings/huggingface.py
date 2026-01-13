"""HuggingFace embedding provider implementation.

Uses the HuggingFace Inference API for embedding generation.
"""
import asyncio
import os
import time
from typing import List, Optional

import requests

from reconly_core.config_types import ConfigField, ProviderConfigSchema
from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)


# Popular HuggingFace embedding models
HUGGINGFACE_EMBEDDING_MODELS = {
    'BAAI/bge-m3': {
        'name': 'BGE-M3',
        'dimension': 1024,
        'description': 'State-of-the-art multilingual embedding model',
    },
    'BAAI/bge-large-en-v1.5': {
        'name': 'BGE Large EN v1.5',
        'dimension': 1024,
        'description': 'High-quality English embedding model',
    },
    'sentence-transformers/all-MiniLM-L6-v2': {
        'name': 'All-MiniLM-L6-v2',
        'dimension': 384,
        'description': 'Fast and efficient, good for general use',
    },
    'sentence-transformers/all-mpnet-base-v2': {
        'name': 'All-MPNet-Base-v2',
        'dimension': 768,
        'description': 'Best quality among sentence transformers',
    },
    'intfloat/e5-large-v2': {
        'name': 'E5 Large v2',
        'dimension': 1024,
        'description': 'Microsoft E5 model, excellent for retrieval',
    },
    'thenlper/gte-large': {
        'name': 'GTE Large',
        'dimension': 1024,
        'description': 'General Text Embeddings model from Alibaba',
    },
}

# Default model
DEFAULT_HUGGINGFACE_EMBEDDING_MODEL = 'BAAI/bge-m3'


class HuggingFaceEmbedding(EmbeddingProvider):
    """Generates embeddings using HuggingFace Inference API.

    Supports any model available on HuggingFace that produces embeddings.
    Requires HUGGINGFACE_API_KEY environment variable.

    Example:
        >>> provider = HuggingFaceEmbedding(model_id='BAAI/bge-m3')
        >>> embeddings = await provider.embed(['Hello world', 'Test text'])
        >>> print(len(embeddings[0]))  # 1024
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout: int = 60,
    ):
        """
        Initialize the HuggingFace embedding provider.

        Args:
            api_key: HuggingFace API token (if not provided, reads from HUGGINGFACE_API_KEY)
            model_id: Full model ID on HuggingFace (e.g., 'BAAI/bge-m3')
            timeout: Request timeout in seconds
        """
        super().__init__(api_key)
        self.api_key = api_key or os.getenv('HUGGINGFACE_API_KEY')

        if not self.api_key:
            raise ValueError(
                "HuggingFace API key required. Set HUGGINGFACE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.model_id = model_id or os.getenv('EMBEDDING_MODEL', DEFAULT_HUGGINGFACE_EMBEDDING_MODEL)
        self.timeout = timeout

        # Get dimension from model config or use default
        model_config = HUGGINGFACE_EMBEDDING_MODELS.get(self.model_id, {})
        self._dimension = model_config.get('dimension', 1024)

        # API endpoint - use feature extraction pipeline
        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_id}"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_provider_name(self) -> str:
        """Get provider name."""
        return 'huggingface'

    def get_dimension(self) -> int:
        """Get embedding vector dimension."""
        return self._dimension

    def get_model_info(self) -> dict:
        """Get model information."""
        return {
            'provider': 'huggingface',
            'model': self.model_id,
            'dimension': self._dimension,
        }

    @classmethod
    def get_capabilities(cls) -> EmbeddingProviderCapabilities:
        """Get provider capabilities."""
        return EmbeddingProviderCapabilities(
            is_local=False,
            requires_api_key=True,
            supports_batch=True,
            max_batch_size=32,  # HuggingFace free tier limit
            max_tokens_per_text=512,
            dimension=1024,  # Default for bge-m3
        )

    def is_available(self) -> bool:
        """Check if provider is available (API key is set)."""
        return self.api_key is not None and len(self.api_key) > 0

    def validate_config(self) -> List[str]:
        """Validate provider configuration."""
        errors = []

        if not self.api_key:
            errors.append(
                "HuggingFace API key is required but not set. "
                "Set HUGGINGFACE_API_KEY environment variable."
            )

        if not self.model_id:
            errors.append("Model ID is required")

        return errors

    def get_config_schema(self) -> ProviderConfigSchema:
        """Get the configuration schema for HuggingFace embedding provider."""
        return ProviderConfigSchema(
            fields=[
                ConfigField(
                    key="api_key",
                    type="string",
                    label="API Key",
                    description="HuggingFace API token",
                    env_var="HUGGINGFACE_API_KEY",
                    editable=False,
                    secret=True,
                    required=True,
                ),
                ConfigField(
                    key="model_id",
                    type="string",
                    label="Model ID",
                    description="HuggingFace model ID (e.g., BAAI/bge-m3)",
                    default=DEFAULT_HUGGINGFACE_EMBEDDING_MODEL,
                    env_var="EMBEDDING_MODEL",
                    editable=True,
                    placeholder="BAAI/bge-m3",
                ),
            ],
            requires_api_key=True,
        )

    @classmethod
    def list_models(cls, api_key: Optional[str] = None) -> List[EmbeddingModelInfo]:
        """List available embedding models."""
        models = []
        for model_id, config in HUGGINGFACE_EMBEDDING_MODELS.items():
            models.append(EmbeddingModelInfo(
                id=model_id,
                name=config['name'],
                provider='huggingface',
                dimension=config['dimension'],
                is_default=(model_id == DEFAULT_HUGGINGFACE_EMBEDDING_MODEL),
            ))
        return models

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts using HuggingFace.

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

        # Process in batches
        batch_size = 32
        all_embeddings = []

        loop = asyncio.get_running_loop()
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = await loop.run_in_executor(
                None, self._embed_batch_sync, batch
            )
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def _embed_batch_sync(
        self,
        texts: List[str],
        max_retries: int = 3
    ) -> List[List[float]]:
        """Synchronous batch embedding with retry logic."""
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json={"inputs": texts, "options": {"wait_for_model": True}},
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    return self._process_embeddings(result)

                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    if attempt < max_retries - 1:
                        wait_time = min(20, 2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RuntimeError(
                            f"Model loading timeout after {max_retries} attempts"
                        )

                elif response.status_code == 401:
                    raise RuntimeError(
                        "HuggingFace authentication failed. "
                        "Check your API key."
                    )

                elif response.status_code == 429:
                    # Rate limited
                    if attempt < max_retries - 1:
                        wait_time = min(30, 5 * (attempt + 1))
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RuntimeError(
                            "HuggingFace rate limit exceeded. Try again later."
                        )

                else:
                    raise RuntimeError(
                        f"HuggingFace API error {response.status_code}: {response.text}"
                    )

            except requests.Timeout:
                if attempt < max_retries - 1:
                    continue
                raise RuntimeError(
                    f"HuggingFace request timed out after {self.timeout}s"
                )

            except requests.RequestException as e:
                raise RuntimeError(f"Request failed: {str(e)}")

        raise RuntimeError("Max retries exceeded")

    def _process_embeddings(self, result: list) -> List[List[float]]:
        """Process API response into embedding vectors.

        HuggingFace feature-extraction returns different shapes depending
        on the model:
        - Some return [batch, sequence, dimension] - need mean pooling
        - Some return [batch, dimension] - already pooled
        """
        if not result:
            raise RuntimeError("HuggingFace returned empty result")

        embeddings = []

        for item in result:
            if isinstance(item, list):
                if isinstance(item[0], list):
                    # Shape: [sequence, dimension] - apply mean pooling
                    # Average across sequence dimension
                    seq_len = len(item)
                    dim = len(item[0])
                    pooled = [0.0] * dim
                    for token_embedding in item:
                        for i, val in enumerate(token_embedding):
                            pooled[i] += val
                    pooled = [v / seq_len for v in pooled]
                    embeddings.append(pooled)
                else:
                    # Shape: [dimension] - already a single embedding
                    embeddings.append(item)
            else:
                raise RuntimeError(f"Unexpected embedding format: {type(item)}")

        return embeddings

