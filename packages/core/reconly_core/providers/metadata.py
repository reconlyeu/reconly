"""Provider-specific metadata for LLM providers.

This module defines the ProviderMetadata dataclass that extends ComponentMetadata
with provider-specific fields for configuration, environment variables, and
availability checking.

Example:
    >>> from reconly_core.providers.metadata import ProviderMetadata
    >>> metadata = ProviderMetadata(
    ...     name="openai",
    ...     display_name="OpenAI",
    ...     description="OpenAI GPT models via API",
    ...     icon="simple-icons:openai",
    ...     requires_api_key=True,
    ...     api_key_env_var="OPENAI_API_KEY",
    ...     api_key_prefix="sk-",
    ... )
    >>> # Get API key from environment
    >>> api_key = metadata.get_api_key()
    >>> # Mask the API key for display
    >>> masked = metadata.mask_api_key("sk-abc123xyz")
    >>> print(masked)  # 'sk-***xyz'
"""
import os
from dataclasses import dataclass, field
from typing import Any

from reconly_core.metadata import ComponentMetadata


@dataclass
class ProviderMetadata(ComponentMetadata):
    """Metadata for LLM providers.

    Extends ComponentMetadata with provider-specific configuration including
    API key handling, base URL configuration, timeouts, and availability checking.

    Attributes:
        name: Internal identifier (e.g., 'openai', 'ollama', 'lmstudio').
        display_name: Human-readable name (e.g., 'OpenAI', 'Ollama', 'LM Studio').
        description: Short description of the provider.
        icon: Icon identifier for UI (e.g., 'simple-icons:openai').
        is_local: True if provider runs locally (Ollama, LMStudio), False for cloud APIs.
        requires_api_key: Whether the provider requires an API key to function.
        api_key_env_var: Environment variable name for API key (e.g., 'OPENAI_API_KEY').
                         None for providers that don't need API keys.
        api_key_prefix: Expected prefix for API keys (e.g., 'sk-' for OpenAI).
                        Used for masking and validation. None if no prefix.
        base_url_env_var: Environment variable for custom base URL (e.g., 'OLLAMA_BASE_URL').
                          None if base URL is not configurable.
        base_url_default: Default base URL for the provider (e.g., 'http://localhost:11434').
                          None for cloud providers with fixed endpoints.
        timeout_env_var: Environment variable for timeout configuration.
                         Defaults to a provider-specific pattern like 'PROVIDER_TIMEOUT_OLLAMA'.
        timeout_default: Default timeout in seconds. Local providers typically need longer timeouts.
        availability_endpoint: Relative endpoint path to check if provider is available
                               (e.g., '/api/tags' for Ollama, '/v1/models' for LMStudio).
                               None for cloud providers that don't support health checks.
        chat_adapter_format: The chat adapter format this provider uses for tool calling
                             (e.g., 'openai', 'anthropic', 'ollama'). If None, uses provider name.
                             Set this when a provider uses another provider's API format
                             (e.g., HuggingFace and LMStudio use 'openai' format).

    Example:
        >>> metadata = ProviderMetadata(
        ...     name="ollama",
        ...     display_name="Ollama",
        ...     description="Local LLM via Ollama server",
        ...     icon="mdi:robot",
        ...     is_local=True,
        ...     requires_api_key=False,
        ...     base_url_env_var="OLLAMA_BASE_URL",
        ...     base_url_default="http://localhost:11434",
        ...     timeout_env_var="PROVIDER_TIMEOUT_OLLAMA",
        ...     timeout_default=900,
        ...     availability_endpoint="/api/tags",
        ... )
    """

    is_local: bool = False
    requires_api_key: bool = True
    api_key_env_var: str | None = None
    api_key_prefix: str | None = None
    base_url_env_var: str | None = None
    base_url_default: str | None = None
    timeout_env_var: str = field(default="PROVIDER_TIMEOUT")
    timeout_default: int = 120
    availability_endpoint: str | None = None
    chat_adapter_format: str | None = None  # API format for chat adapters (e.g., 'openai', 'anthropic', 'ollama'). None means use provider name.
    chat_api_base_url: str | None = None  # Base URL for chat API (for OpenAI-compatible providers with non-standard endpoints)

    def get_api_key(self) -> str | None:
        """Get API key from environment variable.

        Returns the API key from the configured environment variable,
        or None if no environment variable is configured or the variable is not set.

        Returns:
            API key string if available, None otherwise.

        Example:
            >>> import os
            >>> os.environ["OPENAI_API_KEY"] = "sk-test123"
            >>> metadata = ProviderMetadata(
            ...     name="openai", display_name="OpenAI",
            ...     description="OpenAI", api_key_env_var="OPENAI_API_KEY"
            ... )
            >>> metadata.get_api_key()
            'sk-test123'
        """
        if self.api_key_env_var:
            return os.getenv(self.api_key_env_var)
        return None

    def get_base_url(self) -> str | None:
        """Get base URL from environment variable or default.

        Returns the base URL from the configured environment variable if set,
        otherwise returns the default base URL. Returns None if neither is configured.

        Returns:
            Base URL string if available, None otherwise.

        Example:
            >>> metadata = ProviderMetadata(
            ...     name="ollama", display_name="Ollama", description="Ollama",
            ...     base_url_env_var="OLLAMA_BASE_URL",
            ...     base_url_default="http://localhost:11434"
            ... )
            >>> # Returns default if env var not set
            >>> metadata.get_base_url()
            'http://localhost:11434'
        """
        if self.base_url_env_var:
            env_url = os.getenv(self.base_url_env_var)
            if env_url:
                return env_url
        return self.base_url_default

    def get_timeout(self) -> int:
        """Get timeout from environment variable or default.

        Returns the timeout value from the configured environment variable if set
        and valid, otherwise returns the default timeout.

        Returns:
            Timeout in seconds.

        Example:
            >>> import os
            >>> os.environ["PROVIDER_TIMEOUT_OLLAMA"] = "600"
            >>> metadata = ProviderMetadata(
            ...     name="ollama", display_name="Ollama", description="Ollama",
            ...     timeout_env_var="PROVIDER_TIMEOUT_OLLAMA",
            ...     timeout_default=900
            ... )
            >>> metadata.get_timeout()
            600
        """
        env_timeout = os.getenv(self.timeout_env_var)
        if env_timeout:
            try:
                return int(env_timeout)
            except ValueError:
                # Invalid integer in env var, fall back to default
                pass
        return self.timeout_default

    def mask_api_key(self, api_key: str | None) -> str | None:
        """Mask API key for safe display, preserving prefix if configured.

        Masks the middle portion of the API key while preserving the prefix
        (if configured) and last 3 characters for identification.

        Args:
            api_key: The API key to mask. If None or empty, returns None.

        Returns:
            Masked API key string (e.g., 'sk-***xyz'), or None if input is None/empty.

        Example:
            >>> metadata = ProviderMetadata(
            ...     name="openai", display_name="OpenAI", description="OpenAI",
            ...     api_key_prefix="sk-"
            ... )
            >>> metadata.mask_api_key("sk-abc123xyz789")
            'sk-***789'
            >>> metadata.mask_api_key(None)
            None
        """
        if not api_key:
            return None

        # If we have a prefix and the key starts with it, preserve the prefix
        if self.api_key_prefix and api_key.startswith(self.api_key_prefix):
            prefix = self.api_key_prefix
            suffix = api_key[-3:] if len(api_key) > len(prefix) + 3 else ""
            return f"{prefix}***{suffix}"

        # No prefix configured, just show last 3 characters
        suffix = api_key[-3:] if len(api_key) > 3 else ""
        return f"***{suffix}"

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for API responses.

        Extends the base to_dict() to include all provider-specific fields.
        Note: This does NOT include actual API key values, only metadata about them.

        Returns:
            Dictionary with all metadata fields serialized.
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "is_local": self.is_local,
            "requires_api_key": self.requires_api_key,
            "api_key_env_var": self.api_key_env_var,
            "api_key_prefix": self.api_key_prefix,
            "base_url_env_var": self.base_url_env_var,
            "base_url_default": self.base_url_default,
            "timeout_env_var": self.timeout_env_var,
            "timeout_default": self.timeout_default,
            "availability_endpoint": self.availability_endpoint,
            "chat_adapter_format": self.chat_adapter_format,
            "chat_api_base_url": self.chat_api_base_url,
        }
