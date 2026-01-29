"""Chat adapter registry for self-registering tool adapters.

This module provides a registry pattern for chat adapters, allowing adapters
to self-register via decorators. Supports aliases for providers that share
the same adapter format (e.g., LMStudio uses OpenAI's format).

Example:
    >>> from reconly_core.chat.adapters.registry import (
    ...     register_adapter,
    ...     register_adapter_alias,
    ...     get_adapter,
    ...     list_adapters,
    ... )
    >>>
    >>> @register_adapter("openai")
    >>> class OpenAIAdapter(BaseToolAdapter):
    ...     ...
    >>>
    >>> # Create alias for compatible providers
    >>> register_adapter_alias("lmstudio", "openai")
    >>>
    >>> # Get adapter instance
    >>> adapter = get_adapter("openai")  # Returns OpenAIAdapter instance
    >>> adapter = get_adapter("lmstudio")  # Also returns OpenAIAdapter instance
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.chat.adapters.base import BaseToolAdapter

logger = logging.getLogger(__name__)


# Global registry of adapter name -> adapter class or alias target (string)
# String values indicate aliases that resolve to another adapter name
_ADAPTER_REGISTRY: dict[str, type["BaseToolAdapter"] | str] = {}


def register_adapter(name: str):
    """Decorator to register an adapter class in the global registry.

    Use this decorator to make adapters automatically discoverable
    without modifying factory code.

    Args:
        name: Adapter name (e.g., 'openai', 'anthropic', 'ollama')

    Returns:
        Decorator function that registers the class

    Example:
        >>> @register_adapter('openai')
        >>> class OpenAIAdapter(BaseToolAdapter):
        >>>     ...
    """

    def decorator(cls: type["BaseToolAdapter"]) -> type["BaseToolAdapter"]:
        from reconly_core.chat.adapters.base import BaseToolAdapter

        if not issubclass(cls, BaseToolAdapter):
            raise TypeError(
                f"{cls.__name__} must inherit from BaseToolAdapter to be registered"
            )

        if name in _ADAPTER_REGISTRY:
            existing = _ADAPTER_REGISTRY[name]
            if isinstance(existing, str):
                logger.warning(
                    f"Adapter '{name}' was an alias to '{existing}', "
                    f"overriding with {cls.__name__}"
                )
            else:
                logger.warning(
                    f"Adapter '{name}' already registered as {existing.__name__}, "
                    f"overriding with {cls.__name__}"
                )

        _ADAPTER_REGISTRY[name] = cls
        logger.debug(f"Registered adapter '{name}' -> {cls.__name__}")

        return cls

    return decorator


def register_adapter_alias(alias: str, target: str) -> None:
    """Register an alias that resolves to another adapter.

    Use this for providers that are compatible with another provider's
    format (e.g., LMStudio uses OpenAI's API format).

    Args:
        alias: The alias name (e.g., 'lmstudio')
        target: The target adapter name (e.g., 'openai')

    Raises:
        ValueError: If target adapter is not registered

    Example:
        >>> register_adapter_alias("lmstudio", "openai")
        >>> adapter = get_adapter("lmstudio")  # Returns OpenAIAdapter instance
    """
    if alias in _ADAPTER_REGISTRY:
        existing = _ADAPTER_REGISTRY[alias]
        if isinstance(existing, str):
            logger.warning(
                f"Adapter alias '{alias}' already pointed to '{existing}', "
                f"overriding to point to '{target}'"
            )
        else:
            logger.warning(
                f"Adapter '{alias}' was registered as {existing.__name__}, "
                f"overriding with alias to '{target}'"
            )

    _ADAPTER_REGISTRY[alias] = target
    logger.debug(f"Registered adapter alias '{alias}' -> '{target}'")


def _try_register_provider_alias(provider_name: str) -> bool:
    """Try to register an adapter alias from provider metadata.

    This is called lazily when an adapter is requested but not found.
    It checks if the provider exists in the provider registry and has
    a chat_adapter_format defined, then registers the alias.

    Args:
        provider_name: The provider name to check

    Returns:
        True if an alias was registered, False otherwise
    """
    try:
        # Import factory to ensure all providers are registered
        # This triggers the provider module imports which register providers
        import reconly_core.providers.factory  # noqa: F401

        from reconly_core.providers.registry import (
            is_provider_registered,
            get_provider_entry,
        )

        if not is_provider_registered(provider_name):
            return False

        entry = get_provider_entry(provider_name)
        provider_cls = entry.cls

        # Get metadata if available
        if not hasattr(provider_cls, 'metadata'):
            return False

        metadata = provider_cls.metadata
        adapter_format = getattr(metadata, 'chat_adapter_format', None)

        # Need a custom adapter format that's different from provider name
        if not adapter_format or adapter_format == provider_name:
            return False

        # Check if target adapter exists
        if adapter_format not in _ADAPTER_REGISTRY:
            return False

        # Register the alias
        _ADAPTER_REGISTRY[provider_name] = adapter_format
        logger.debug(
            f"Lazy-registered adapter alias '{provider_name}' -> '{adapter_format}' "
            f"from provider metadata"
        )
        return True

    except Exception as e:
        logger.debug(f"Could not lazy-register adapter for '{provider_name}': {e}")
        return False


def get_adapter(provider_name: str) -> "BaseToolAdapter":
    """Get an adapter instance by provider name.

    Resolves aliases automatically. Returns a fresh instance since
    adapters are stateless.

    If the provider is not directly registered, this function will attempt
    to register it lazily by checking the provider's metadata for a
    chat_adapter_format field.

    Args:
        provider_name: Provider name or alias (e.g., 'openai', 'lmstudio')

    Returns:
        Adapter instance (not class)

    Raises:
        ValueError: If provider name is not registered

    Example:
        >>> adapter = get_adapter('openai')
        >>> formatted = adapter.format_tools(tools)
    """
    # Try lazy registration if not found
    if provider_name not in _ADAPTER_REGISTRY:
        if not _try_register_provider_alias(provider_name):
            available = list_adapters()
            raise ValueError(
                f"Unknown adapter '{provider_name}'. "
                f"Available adapters: {available}."
            )

    entry = _ADAPTER_REGISTRY[provider_name]

    # Resolve alias
    if isinstance(entry, str):
        target_name = entry
        if target_name not in _ADAPTER_REGISTRY:
            raise ValueError(
                f"Adapter alias '{provider_name}' points to '{target_name}', "
                f"but '{target_name}' is not registered."
            )
        entry = _ADAPTER_REGISTRY[target_name]
        if isinstance(entry, str):
            raise ValueError(
                f"Adapter alias chain detected: '{provider_name}' -> '{target_name}' -> '{entry}'. "
                f"Aliases cannot point to other aliases."
            )

    # Return fresh instance
    return entry()


def list_adapters() -> list[str]:
    """List all registered adapter names (excluding aliases).

    Returns:
        List of adapter names (e.g., ['anthropic', 'ollama', 'openai'])

    Example:
        >>> list_adapters()
        ['anthropic', 'ollama', 'openai']
    """
    return sorted([
        name for name, entry in _ADAPTER_REGISTRY.items()
        if not isinstance(entry, str)
    ])


def list_adapter_aliases() -> dict[str, str]:
    """List all registered adapter aliases.

    Returns:
        Dict mapping alias names to their target adapter names

    Example:
        >>> list_adapter_aliases()
        {'lmstudio': 'openai'}
    """
    return {
        name: target for name, target in _ADAPTER_REGISTRY.items()
        if isinstance(target, str)
    }


def is_adapter_registered(name: str) -> bool:
    """Check if an adapter or alias is registered.

    Args:
        name: Adapter name or alias to check

    Returns:
        True if registered, False otherwise
    """
    return name in _ADAPTER_REGISTRY
