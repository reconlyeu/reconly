"""Embedding providers for RAG knowledge system.

This module provides a factory function to get embedding providers
following the same pattern as the summarizer module.

Usage:
    >>> from reconly_core.rag.embeddings import get_embedding_provider
    >>> provider = get_embedding_provider()  # Uses default (ollama)
    >>> embeddings = await provider.embed(['text1', 'text2'])

Providers:
    - ollama: Local embedding via Ollama server (default)
    - openai: OpenAI embedding API (text-embedding-3-small/large)
    - huggingface: HuggingFace Inference API
    - lmstudio: Local embedding via LMStudio's OpenAI-compatible API
"""
import os
from typing import Optional, TYPE_CHECKING

from reconly_core.rag.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderCapabilities,
    EmbeddingModelInfo,
)
from reconly_core.rag.embeddings.ollama import OllamaEmbedding, OLLAMA_EMBEDDING_MODELS
from reconly_core.rag.embeddings.openai import OpenAIEmbedding, OPENAI_EMBEDDING_MODELS
from reconly_core.rag.embeddings.huggingface import HuggingFaceEmbedding, HUGGINGFACE_EMBEDDING_MODELS
from reconly_core.rag.embeddings.lmstudio import LMStudioEmbedding, LMSTUDIO_EMBEDDING_MODELS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Registry of embedding providers
_EMBEDDING_PROVIDERS = {
    'ollama': OllamaEmbedding,
    'openai': OpenAIEmbedding,
    'huggingface': HuggingFaceEmbedding,
    'lmstudio': LMStudioEmbedding,
}

# Default provider
DEFAULT_EMBEDDING_PROVIDER = 'ollama'
DEFAULT_EMBEDDING_MODEL = 'bge-m3'


def _get_setting_with_db_fallback(
    key: str,
    db: Optional["Session"] = None,
    env_var: Optional[str] = None,
    default: Optional[str] = None
) -> Optional[str]:
    """
    Get a setting value using priority: DB > env > default.

    Args:
        key: Setting key for SettingsService
        db: Optional database session
        env_var: Environment variable name
        default: Default value

    Returns:
        The effective value
    """
    # Priority 1: Database via SettingsService
    if db is not None:
        try:
            from reconly_core.services.settings_service import SettingsService
            service = SettingsService(db)
            value = service.get(key)
            if value is not None:
                return value
        except Exception:
            pass  # Fall through to env var

    # Priority 2: Environment variable
    if env_var:
        env_value = os.getenv(env_var)
        if env_value is not None:
            return env_value

    # Priority 3: Default
    return default


def get_embedding_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    db: Optional["Session"] = None,
    **kwargs
) -> EmbeddingProvider:
    """
    Get an embedding provider instance.

    Similar to get_summarizer() but for embeddings.

    Args:
        provider: Provider name ('ollama', 'openai', 'huggingface')
                 If None, reads from EMBEDDING_PROVIDER env var or defaults to 'ollama'
        model: Model identifier. If None, uses provider's default.
        api_key: API key for cloud providers (optional, reads from env)
        db: Optional database session for reading settings from DB
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured EmbeddingProvider instance

    Raises:
        ValueError: If provider is unknown

    Example:
        >>> # Use default (Ollama with bge-m3)
        >>> provider = get_embedding_provider()
        >>>
        >>> # Use OpenAI
        >>> provider = get_embedding_provider('openai', model='text-embedding-3-large')
        >>>
        >>> # Use HuggingFace
        >>> provider = get_embedding_provider('huggingface', model_id='BAAI/bge-m3')
    """
    # Get provider from settings (DB > env > default)
    if provider is None:
        provider = _get_setting_with_db_fallback(
            "embedding.provider",
            db=db,
            env_var="EMBEDDING_PROVIDER",
            default=DEFAULT_EMBEDDING_PROVIDER
        )

    # Validate provider
    if provider not in _EMBEDDING_PROVIDERS:
        available = list(_EMBEDDING_PROVIDERS.keys())
        raise ValueError(
            f"Unknown embedding provider: {provider}. "
            f"Available providers: {available}"
        )

    # Get model from settings if not specified
    if model is None:
        model = _get_setting_with_db_fallback(
            "embedding.model",
            db=db,
            env_var="EMBEDDING_MODEL",
            default=None  # Let provider use its default
        )

    # Get provider class
    provider_class = _EMBEDDING_PROVIDERS[provider]

    # Initialize based on provider type
    if provider == 'ollama':
        return provider_class(
            model=model,
            base_url=kwargs.get('base_url'),
            timeout=kwargs.get('timeout', 120),
        )

    elif provider == 'openai':
        return provider_class(
            api_key=api_key,
            model=model,
            base_url=kwargs.get('base_url'),
        )

    elif provider == 'huggingface':
        return provider_class(
            api_key=api_key,
            model_id=model,
            timeout=kwargs.get('timeout', 60),
        )

    elif provider == 'lmstudio':
        return provider_class(
            model=model,
            base_url=kwargs.get('base_url'),
            timeout=kwargs.get('timeout', 120),
        )

    else:
        # Generic initialization
        return provider_class(api_key=api_key, **kwargs)


def list_embedding_providers() -> list[str]:
    """
    List all available embedding provider names.

    Returns:
        List of provider names
    """
    return list(_EMBEDDING_PROVIDERS.keys())


def list_embedding_models(provider: Optional[str] = None) -> dict[str, list[EmbeddingModelInfo]]:
    """
    List available models by provider.

    Args:
        provider: Optional provider name to filter. If None, returns all.

    Returns:
        Dictionary mapping provider names to lists of model info
    """
    result = {}

    providers = [provider] if provider else list(_EMBEDDING_PROVIDERS.keys())

    for p in providers:
        if p not in _EMBEDDING_PROVIDERS:
            continue

        provider_class = _EMBEDDING_PROVIDERS[p]
        result[p] = provider_class.list_models()

    return result


def get_embedding_dimension(
    provider: str = DEFAULT_EMBEDDING_PROVIDER,
    model: Optional[str] = None
) -> int:
    """
    Get the embedding dimension for a provider/model combination.

    Useful for database schema configuration.

    Args:
        provider: Provider name
        model: Model name (uses provider default if None)

    Returns:
        Embedding dimension as integer

    Example:
        >>> get_embedding_dimension('ollama', 'bge-m3')
        1024
        >>> get_embedding_dimension('openai', 'text-embedding-3-large')
        3072
    """
    # Provider configurations: (model_registry, default_model, default_dimension)
    provider_configs = {
        'ollama': (OLLAMA_EMBEDDING_MODELS, 'bge-m3', 1024),
        'openai': (OPENAI_EMBEDDING_MODELS, 'text-embedding-3-small', 1536),
        'huggingface': (HUGGINGFACE_EMBEDDING_MODELS, 'BAAI/bge-m3', 1024),
        'lmstudio': (LMSTUDIO_EMBEDDING_MODELS, 'nomic-embed-text', 768),
    }

    config = provider_configs.get(provider)
    if config is None:
        return 1024  # Default for unknown providers

    model_registry, default_model, default_dimension = config
    effective_model = model or default_model
    return model_registry.get(effective_model, {}).get('dimension', default_dimension)


__all__ = [
    # Factory
    'get_embedding_provider',
    'list_embedding_providers',
    'list_embedding_models',
    'get_embedding_dimension',
    # Base classes
    'EmbeddingProvider',
    'EmbeddingProviderCapabilities',
    'EmbeddingModelInfo',
    # Providers
    'OllamaEmbedding',
    'OpenAIEmbedding',
    'HuggingFaceEmbedding',
    'LMStudioEmbedding',
]
