"""API key management for LLM providers."""
import os
from typing import Optional


class ApiKeyManager:
    """Manages API key resolution for LLM providers.

    Resolves API keys using provider metadata first, falling back
    to a hardcoded environment variable map for legacy providers.
    """

    # Fallback environment variable map for providers without metadata
    _ENV_VAR_MAP = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'openai': 'OPENAI_API_KEY',
        'huggingface': 'HUGGINGFACE_API_KEY',
    }

    @classmethod
    def get_api_key(cls, provider_name: str) -> Optional[str]:
        """Get API key for a provider.

        Resolution order:
        1. Provider metadata (metadata.get_api_key())
        2. Hardcoded environment variable map

        Args:
            provider_name: Name of the provider (e.g., 'openai', 'anthropic')

        Returns:
            API key if found, None otherwise
        """
        # Avoid circular import — import here
        from reconly_core.providers.factory import is_provider_registered, get_provider

        # Try to get API key from provider metadata
        if is_provider_registered(provider_name):
            try:
                provider_class = get_provider(provider_name)
                metadata = provider_class.get_metadata()
                return metadata.get_api_key()
            except (AttributeError, NotImplementedError):
                pass

        # Fallback: hardcoded map for providers without metadata
        env_var = cls._ENV_VAR_MAP.get(provider_name)
        if env_var:
            return os.getenv(env_var)
        return None
