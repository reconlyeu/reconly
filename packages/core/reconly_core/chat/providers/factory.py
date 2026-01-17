"""Provider factory for creating chat providers with automatic selection and fallback.

This module provides factory functions to create chat providers based on
configuration, environment variables, or automatic detection. It handles:

- Provider selection based on available credentials
- Automatic fallback when primary provider is unavailable
- Caching of provider instances
- Configuration validation

Environment Variables:
    DEFAULT_CHAT_PROVIDER: Preferred provider (openai, anthropic, ollama)
    OPENAI_API_KEY: Enables OpenAI provider
    ANTHROPIC_API_KEY: Enables Anthropic provider
    OLLAMA_BASE_URL: Configures Ollama server location

Example:
    >>> from reconly_core.chat.providers import create_provider, get_default_provider
    >>>
    >>> # Get default provider based on environment
    >>> provider = get_default_provider()
    >>>
    >>> # Create specific provider
    >>> openai = create_provider("openai", model="gpt-4o")
    >>>
    >>> # Create with fallback
    >>> provider = create_provider_with_fallback(
    ...     preferred="anthropic",
    ...     fallback=["openai", "ollama"]
    ... )
"""

from __future__ import annotations

import logging
import os
from typing import Any

from reconly_core.chat.providers.base import (
    BaseChatProvider,
    ChatProviderError,
    AuthenticationError,
)

logger = logging.getLogger(__name__)


# Provider priority order for auto-detection
DEFAULT_PROVIDER_PRIORITY = ["anthropic", "openai", "ollama"]


class ProviderFactoryError(ChatProviderError):
    """Error creating or configuring a provider."""

    pass


class NoAvailableProviderError(ChatProviderError):
    """No providers are available."""

    pass


def create_provider(
    provider_name: str,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatProvider:
    """Create a chat provider by name.

    Args:
        provider_name: Name of the provider (openai, anthropic, ollama).
        model: Optional model name override.
        **kwargs: Additional provider-specific configuration.

    Returns:
        Configured chat provider instance.

    Raises:
        ProviderFactoryError: If the provider name is unknown.
        AuthenticationError: If required credentials are missing.

    Example:
        >>> provider = create_provider("openai", model="gpt-4-turbo")
        >>> provider = create_provider("anthropic", max_tokens=2048)
        >>> provider = create_provider("ollama", base_url="http://gpu-server:11434")
    """
    provider_name = provider_name.lower()

    if provider_name == "openai":
        from reconly_core.chat.providers.openai_provider import OpenAIChatProvider

        if model:
            kwargs["model"] = model
        return OpenAIChatProvider(**kwargs)

    elif provider_name == "anthropic":
        from reconly_core.chat.providers.anthropic_provider import AnthropicChatProvider

        if model:
            kwargs["model"] = model
        return AnthropicChatProvider(**kwargs)

    elif provider_name == "ollama":
        from reconly_core.chat.providers.ollama_provider import OllamaChatProvider

        if model:
            kwargs["model"] = model
        return OllamaChatProvider(**kwargs)

    else:
        raise ProviderFactoryError(
            f"Unknown provider: {provider_name}. "
            f"Supported providers: openai, anthropic, ollama",
            provider=provider_name,
        )


def get_available_providers() -> list[str]:
    """Get list of providers that appear to be configured.

    Checks environment variables and basic availability to determine
    which providers can be used.

    Returns:
        List of provider names that are available.

    Example:
        >>> available = get_available_providers()
        >>> print(available)  # ['anthropic', 'ollama']
    """
    available = []

    # Check Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("anthropic")

    # Check OpenAI
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")

    # Check Ollama (always potentially available if server is running)
    try:
        import httpx

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        if response.status_code == 200:
            available.append("ollama")
    except Exception:
        pass

    return available


def get_default_provider(
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatProvider:
    """Get the default chat provider based on environment configuration.

    Uses DEFAULT_CHAT_PROVIDER env var if set, otherwise auto-detects
    based on available credentials in priority order.

    Priority order: anthropic > openai > ollama

    Args:
        model: Optional model name override.
        **kwargs: Additional provider configuration.

    Returns:
        Configured chat provider instance.

    Raises:
        NoAvailableProviderError: If no providers are available.

    Example:
        >>> provider = get_default_provider()
        >>> provider = get_default_provider(model="gpt-4o")
    """
    # Check for explicit preference
    preferred = os.getenv("DEFAULT_CHAT_PROVIDER", "").lower()

    if preferred:
        try:
            return create_provider(preferred, model=model, **kwargs)
        except AuthenticationError:
            logger.warning(
                f"Preferred provider '{preferred}' not available, trying fallbacks"
            )
        except ProviderFactoryError:
            logger.warning(
                f"Unknown preferred provider '{preferred}', trying auto-detection"
            )

    # Auto-detect based on priority
    for provider_name in DEFAULT_PROVIDER_PRIORITY:
        try:
            provider = create_provider(provider_name, model=model, **kwargs)
            if provider.is_available():
                logger.info(f"Using {provider_name} as default chat provider")
                return provider
        except AuthenticationError:
            continue
        except Exception as e:
            logger.debug(f"Provider {provider_name} not available: {e}")
            continue

    raise NoAvailableProviderError(
        "No chat providers are available. Configure one of:\n"
        "  - ANTHROPIC_API_KEY for Anthropic Claude\n"
        "  - OPENAI_API_KEY for OpenAI GPT\n"
        "  - Ollama server at OLLAMA_BASE_URL (default: http://localhost:11434)"
    )


def create_provider_with_fallback(
    preferred: str,
    fallback: list[str] | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatProvider:
    """Create a provider with fallback options.

    Tries to create the preferred provider, falling back to alternatives
    if the preferred one is unavailable.

    Args:
        preferred: Preferred provider name.
        fallback: List of fallback provider names (default: all others).
        model: Optional model name override.
        **kwargs: Additional provider configuration.

    Returns:
        Configured chat provider instance.

    Raises:
        NoAvailableProviderError: If no providers are available.

    Example:
        >>> # Try Anthropic, fall back to OpenAI or Ollama
        >>> provider = create_provider_with_fallback("anthropic")
        >>>
        >>> # Try Ollama, fall back only to OpenAI
        >>> provider = create_provider_with_fallback("ollama", fallback=["openai"])
    """
    if fallback is None:
        # Default fallback is all other providers in priority order
        fallback = [p for p in DEFAULT_PROVIDER_PRIORITY if p != preferred]

    providers_to_try = [preferred] + fallback
    errors = []

    for provider_name in providers_to_try:
        try:
            provider = create_provider(provider_name, model=model, **kwargs)
            if provider.is_available():
                if provider_name != preferred:
                    logger.info(
                        f"Using fallback provider '{provider_name}' "
                        f"(preferred '{preferred}' unavailable)"
                    )
                return provider
        except AuthenticationError as e:
            errors.append(f"{provider_name}: {e}")
        except Exception as e:
            errors.append(f"{provider_name}: {e}")

    error_details = "\n".join(f"  - {e}" for e in errors)
    raise NoAvailableProviderError(
        f"No providers available. Tried: {', '.join(providers_to_try)}\n"
        f"Errors:\n{error_details}"
    )


def get_provider_info() -> dict[str, dict[str, Any]]:
    """Get information about all available providers.

    Returns detailed status and configuration for each provider,
    useful for debugging and status pages.

    Returns:
        Dictionary mapping provider names to info dicts.

    Example:
        >>> info = get_provider_info()
        >>> for name, data in info.items():
        ...     print(f"{name}: {'available' if data['available'] else 'unavailable'}")
    """
    info = {}

    # OpenAI
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    openai_info = {
        "available": bool(openai_api_key),
        "configured": bool(openai_api_key),
        "has_api_key": bool(openai_api_key),
        "api_key_prefix": openai_api_key[:10] + "..." if openai_api_key else None,
        "base_url": os.getenv("OPENAI_BASE_URL"),
        "default_model": "gpt-4o",
        "supports_tools": True,
        "supports_streaming": True,
        "is_local": False,
    }
    info["openai"] = openai_info

    # Anthropic
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_info = {
        "available": bool(anthropic_api_key),
        "configured": bool(anthropic_api_key),
        "has_api_key": bool(anthropic_api_key),
        "api_key_prefix": anthropic_api_key[:10] + "..." if anthropic_api_key else None,
        "default_model": "claude-sonnet-4-20250514",
        "supports_tools": True,
        "supports_streaming": True,
        "is_local": False,
    }
    info["anthropic"] = anthropic_info

    # Ollama
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_available = False
    ollama_models = []

    try:
        import httpx

        response = httpx.get(f"{ollama_base_url}/api/tags", timeout=2.0)
        if response.status_code == 200:
            ollama_available = True
            data = response.json()
            ollama_models = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    ollama_info = {
        "available": ollama_available,
        "configured": True,  # Ollama doesn't need explicit config
        "has_api_key": False,  # Ollama doesn't use API keys
        "base_url": ollama_base_url,
        "default_model": os.getenv("OLLAMA_MODEL", "llama3.2"),
        "models": ollama_models,
        "supports_tools": False,  # Prompt-based only
        "supports_streaming": True,
        "is_local": True,
    }
    info["ollama"] = ollama_info

    return info


# Provider instance cache for reuse
_provider_cache: dict[str, BaseChatProvider] = {}


def get_cached_provider(
    provider_name: str,
    model: str | None = None,
    **kwargs: Any,
) -> BaseChatProvider:
    """Get a cached provider instance or create a new one.

    Caches provider instances by name+model to avoid recreating clients.
    Useful when making multiple requests with the same configuration.

    Args:
        provider_name: Name of the provider.
        model: Optional model name.
        **kwargs: Additional provider configuration.

    Returns:
        Cached or newly created provider instance.

    Example:
        >>> # First call creates the provider
        >>> p1 = get_cached_provider("openai", model="gpt-4o")
        >>> # Second call returns the same instance
        >>> p2 = get_cached_provider("openai", model="gpt-4o")
        >>> assert p1 is p2
    """
    cache_key = f"{provider_name}:{model or 'default'}"

    if cache_key not in _provider_cache:
        _provider_cache[cache_key] = create_provider(
            provider_name, model=model, **kwargs
        )

    return _provider_cache[cache_key]


def clear_provider_cache() -> None:
    """Clear the provider instance cache.

    Call this if you need to refresh provider configurations or
    release resources.
    """
    _provider_cache.clear()
