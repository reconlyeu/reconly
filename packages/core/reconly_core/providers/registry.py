"""Provider registry for self-registering LLM providers."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reconly_core.config_types import ProviderConfigSchema
    from reconly_core.extensions.types import ExtensionMetadata
    from reconly_core.providers.base import BaseProvider

logger = logging.getLogger(__name__)


@dataclass
class ProviderRegistryEntry:
    """Entry in the provider registry with extension metadata."""
    cls: type['BaseProvider']
    is_extension: bool = False
    metadata: 'ExtensionMetadata | None' = None
    config_schema: 'ProviderConfigSchema | None' = None


# Global registry of provider name -> provider entry
_PROVIDER_REGISTRY: dict[str, ProviderRegistryEntry] = {}


def register_provider(
    name: str,
    is_extension: bool = False,
    metadata: 'ExtensionMetadata | None' = None,
):
    """
    Decorator to register a provider class in the global registry.

    Contributors can use this decorator to make their provider automatically
    discoverable without modifying factory.py.

    Args:
        name: Provider name (e.g., 'ollama', 'openai', 'anthropic')
        is_extension: Whether this is an external extension (default False)
        metadata: Extension metadata if this is an extension

    Returns:
        Decorator function that registers the class

    Example:
        >>> @register_provider('ollama')
        >>> class OllamaProvider(BaseProvider):
        >>>     ...
    """
    def decorator(cls: type['BaseProvider']) -> type['BaseProvider']:
        from reconly_core.providers.base import BaseProvider

        if not issubclass(cls, BaseProvider):
            raise TypeError(
                f"{cls.__name__} must inherit from BaseProvider to be registered as a provider"
            )

        if name in _PROVIDER_REGISTRY:
            existing = _PROVIDER_REGISTRY[name]
            logger.warning(
                f"Provider '{name}' already registered as {existing.cls.__name__}, "
                f"overriding with {cls.__name__}"
            )

        # Get config schema and register settings
        config_schema = _get_provider_config_schema(name, cls)

        _PROVIDER_REGISTRY[name] = ProviderRegistryEntry(
            cls=cls,
            is_extension=is_extension,
            metadata=metadata,
            config_schema=config_schema,
        )
        logger.debug(f"Registered provider '{name}' -> {cls.__name__}")

        return cls

    return decorator


def _get_provider_config_schema(
    name: str, cls: type['BaseProvider']
) -> 'ProviderConfigSchema | None':
    """Get config schema from provider and register settings.

    Uses importlib to avoid circular dependency with services module.

    Returns:
        The provider's config schema, or None if unavailable.
    """
    import importlib

    try:
        # Try with dummy api_key for providers that require it
        try:
            instance = cls(api_key="dummy_key_for_schema")
        except TypeError:
            instance = cls()

        config_schema = instance.get_config_schema()
        if config_schema.fields:
            settings_registry = importlib.import_module(
                'reconly_core.services.settings_registry'
            )
            settings_registry.register_component_settings("provider", name, config_schema)
            logger.debug(f"Auto-registered settings for provider '{name}'")
        return config_schema
    except Exception as e:
        logger.warning(f"Failed to get config schema for provider '{name}': {e}")
        return None


def get_provider(name: str) -> type['BaseProvider']:
    """
    Get a provider class by name.

    Args:
        name: Provider name (e.g., 'ollama', 'openai')

    Returns:
        Provider class (not instantiated)

    Raises:
        ValueError: If provider name is not registered

    Example:
        >>> OllamaClass = get_provider('ollama')
        >>> provider = OllamaClass(api_key='...')
    """
    if name not in _PROVIDER_REGISTRY:
        available = list(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available providers: {available}. "
            f"See docs/ADDING_PROVIDERS.md for information on adding new providers."
        )

    return _PROVIDER_REGISTRY[name].cls


def get_provider_entry(name: str) -> ProviderRegistryEntry:
    """
    Get the full registry entry for a provider.

    Args:
        name: Provider name (e.g., 'ollama', 'openai')

    Returns:
        ProviderRegistryEntry with class and extension info

    Raises:
        ValueError: If provider name is not registered
    """
    if name not in _PROVIDER_REGISTRY:
        available = list(_PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available providers: {available}."
        )

    return _PROVIDER_REGISTRY[name]


def list_providers() -> list[str]:
    """
    List all registered provider names.

    Returns:
        List of provider names (e.g., ['anthropic', 'huggingface', 'ollama'])

    Example:
        >>> list_providers()
        ['anthropic', 'huggingface', 'ollama', 'openai']
    """
    return list(_PROVIDER_REGISTRY.keys())


def list_extension_providers() -> list[str]:
    """
    List only external extension providers.

    Returns:
        List of extension provider names
    """
    return [
        name for name, entry in _PROVIDER_REGISTRY.items()
        if entry.is_extension
    ]


def list_builtin_providers() -> list[str]:
    """
    List only built-in (non-extension) providers.

    Returns:
        List of built-in provider names
    """
    return [
        name for name, entry in _PROVIDER_REGISTRY.items()
        if not entry.is_extension
    ]


def is_provider_extension(name: str) -> bool:
    """
    Check if a provider is an external extension.

    Args:
        name: Provider name to check

    Returns:
        True if provider is an extension, False if built-in or not found
    """
    if name not in _PROVIDER_REGISTRY:
        return False
    return _PROVIDER_REGISTRY[name].is_extension


def get_provider_by_capability(capability: str, value: bool = True) -> list[str]:
    """
    Find providers by capability.

    Args:
        capability: Capability name (e.g., 'is_local', 'requires_api_key')
        value: Expected value for the capability (default: True)

    Returns:
        List of provider names matching the capability

    Example:
        >>> get_provider_by_capability('is_local')
        ['ollama']
        >>> get_provider_by_capability('requires_api_key', False)
        ['ollama']
    """
    matching = []

    for provider_name, entry in _PROVIDER_REGISTRY.items():
        try:
            capabilities = entry.cls.get_capabilities()
            if hasattr(capabilities, capability):
                if getattr(capabilities, capability) == value:
                    matching.append(provider_name)
        except Exception as e:
            logger.debug(f"Could not get capabilities for {provider_name}: {e}")
            continue

    return matching


def is_provider_registered(name: str) -> bool:
    """
    Check if a provider is registered.

    Args:
        name: Provider name to check

    Returns:
        True if provider is registered, False otherwise
    """
    return name in _PROVIDER_REGISTRY


def get_extension_info(name: str) -> dict | None:
    """
    Get extension information for a provider if it's an extension.

    Args:
        name: Provider name

    Returns:
        Dict with extension info if provider is an extension, None otherwise
    """
    if name not in _PROVIDER_REGISTRY:
        return None

    entry = _PROVIDER_REGISTRY[name]
    if not entry.is_extension:
        return None

    return {
        "name": name,
        "is_extension": True,
        "metadata": entry.metadata.to_dict() if entry.metadata else None,
    }
