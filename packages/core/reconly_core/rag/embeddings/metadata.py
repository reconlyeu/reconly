"""Embedding provider-specific metadata for embedding providers.

This module defines the EmbeddingProviderMetadata dataclass that extends ComponentMetadata
with embedding provider-specific fields for API key requirements, base URL support, and
model configuration.

Example:
    >>> from reconly_core.rag.embeddings.metadata import EmbeddingProviderMetadata
    >>> metadata = EmbeddingProviderMetadata(
    ...     name="ollama",
    ...     display_name="Ollama",
    ...     description="Local embedding via Ollama server",
    ...     icon="simple-icons:ollama",
    ...     requires_api_key=False,
    ...     supports_base_url=True,
    ...     is_local=True,
    ...     default_model="bge-m3",
    ... )
    >>> metadata.to_dict()
    {'name': 'ollama', 'display_name': 'Ollama', ...}
"""
from dataclasses import dataclass
from typing import Any

from reconly_core.metadata import ComponentMetadata


@dataclass
class EmbeddingProviderMetadata(ComponentMetadata):
    """Metadata for embedding providers.

    Extends ComponentMetadata with embedding provider-specific configuration including
    API key requirements, base URL support, model parameter naming, and local/remote
    classification.

    Attributes:
        name: Internal identifier (e.g., 'ollama', 'openai', 'huggingface').
        display_name: Human-readable name (e.g., 'Ollama', 'OpenAI', 'HuggingFace').
        description: Short description of the provider.
        icon: Icon identifier for UI (e.g., 'simple-icons:ollama', 'simple-icons:openai').
        requires_api_key: Whether the provider requires an API key for authentication.
                          Cloud providers typically require this, local providers don't.
        supports_base_url: Whether the provider supports a custom base URL configuration.
                           Useful for self-hosted instances or proxies.
        model_param_name: Parameter name used for model selection (e.g., 'model', 'model_id').
                          Different providers may use different parameter names.
        is_local: Whether the provider runs locally without external API calls.
                  Local providers (Ollama, LMStudio) run on the user's machine.
        default_model: Default model identifier for the provider.
                       Used when no model is explicitly specified.

    Example:
        >>> metadata = EmbeddingProviderMetadata(
        ...     name="openai",
        ...     display_name="OpenAI",
        ...     description="OpenAI embedding API (text-embedding-3-small/large)",
        ...     icon="simple-icons:openai",
        ...     requires_api_key=True,
        ...     supports_base_url=True,
        ...     model_param_name="model",
        ...     is_local=False,
        ...     default_model="text-embedding-3-small",
        ... )
    """

    requires_api_key: bool = True
    supports_base_url: bool = False
    model_param_name: str = "model"
    is_local: bool = False
    default_model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for API responses.

        Extends the base to_dict() to include all embedding provider-specific fields.

        Returns:
            Dictionary with all metadata fields serialized.
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "requires_api_key": self.requires_api_key,
            "supports_base_url": self.supports_base_url,
            "model_param_name": self.model_param_name,
            "is_local": self.is_local,
            "default_model": self.default_model,
        }
