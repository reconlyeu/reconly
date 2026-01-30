"""OAuth provider registry for email authentication.

This module provides a registry pattern for OAuth email providers (Gmail, Outlook, etc.)
allowing dynamic registration and discovery of OAuth providers with their configuration
and authentication flow functions.

Usage:
    >>> from reconly_core.email.oauth_registry import (
    ...     OAuthProviderMetadata,
    ...     register_oauth_provider,
    ...     get_oauth_provider,
    ...     list_oauth_providers,
    ... )
    >>>
    >>> # Register a new provider
    >>> @register_oauth_provider
    ... def gmail_provider():
    ...     return OAuthProviderMetadata(
    ...         name="gmail",
    ...         display_name="Gmail",
    ...         ...
    ...     )
    >>>
    >>> # Get a provider
    >>> provider = get_oauth_provider("gmail")
    >>> if provider and provider.is_configured():
    ...     auth_url = provider.auth_url_generator(redirect_uri, state, code_challenge)

Providers:
    - gmail: Google Gmail via OAuth2 (requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
    - outlook: Microsoft Outlook/365 via OAuth2 (requires MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from reconly_core.metadata import ComponentMetadata


# Type aliases for OAuth callable signatures
AuthUrlGenerator = Callable[[str, str, str], str]  # (redirect_uri, state, code_challenge) -> url
TokenExchanger = Callable[[str, str, str], Any]  # (code, redirect_uri, code_verifier) -> tokens
TokenRevoker = Callable[[str], bool]  # (token) -> success


@dataclass
class OAuthProviderMetadata(ComponentMetadata):
    """Metadata for OAuth email providers.

    Extends ComponentMetadata with OAuth-specific configuration including
    environment variable names for credentials, OAuth scopes, and callable
    functions for the OAuth flow (authorization URL generation, token exchange,
    and token revocation).

    Attributes:
        name: Internal identifier (e.g., 'gmail', 'outlook').
              Should be lowercase with no spaces.
        display_name: Human-readable name (e.g., 'Gmail', 'Outlook / Microsoft 365').
        description: Short description of the provider.
        icon: Icon identifier for UI (e.g., 'mdi:google', 'mdi:microsoft').
        client_id_env_var: Environment variable name for OAuth client ID
                           (e.g., 'GOOGLE_CLIENT_ID').
        client_secret_env_var: Environment variable name for OAuth client secret
                               (e.g., 'GOOGLE_CLIENT_SECRET').
        scopes: List of OAuth scopes required by this provider.
        auth_url_generator: Function to generate the authorization URL.
                            Signature: (redirect_uri, state, code_challenge) -> str
        token_exchanger: Function to exchange authorization code for tokens.
                         Signature: (code, redirect_uri, code_verifier) -> tokens
        token_revoker: Function to revoke OAuth tokens.
                       Signature: (token) -> bool

    Example:
        >>> from reconly_core.email.gmail import (
        ...     generate_gmail_auth_url,
        ...     exchange_gmail_code,
        ...     revoke_gmail_token,
        ...     GMAIL_SCOPES,
        ... )
        >>> metadata = OAuthProviderMetadata(
        ...     name="gmail",
        ...     display_name="Gmail",
        ...     description="Google Gmail with OAuth2 authentication",
        ...     icon="mdi:google",
        ...     client_id_env_var="GOOGLE_CLIENT_ID",
        ...     client_secret_env_var="GOOGLE_CLIENT_SECRET",
        ...     scopes=GMAIL_SCOPES,
        ...     auth_url_generator=generate_gmail_auth_url,
        ...     token_exchanger=exchange_gmail_code,
        ...     token_revoker=revoke_gmail_token,
        ... )
        >>> metadata.is_configured()
        True  # If env vars are set
    """

    client_id_env_var: str = ""
    client_secret_env_var: str = ""
    scopes: list[str] = field(default_factory=list)
    auth_url_generator: AuthUrlGenerator | None = None
    token_exchanger: TokenExchanger | None = None
    token_revoker: TokenRevoker | None = None

    def is_configured(self) -> bool:
        """Check if this provider's OAuth credentials are configured.

        Verifies that both the client ID and client secret environment variables
        are set and non-empty.

        Returns:
            True if both environment variables are set, False otherwise.

        Example:
            >>> metadata = OAuthProviderMetadata(
            ...     name="gmail",
            ...     client_id_env_var="GOOGLE_CLIENT_ID",
            ...     client_secret_env_var="GOOGLE_CLIENT_SECRET",
            ...     ...
            ... )
            >>> # Returns True if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set
            >>> metadata.is_configured()
        """
        client_id = os.environ.get(self.client_id_env_var, "")
        client_secret = os.environ.get(self.client_secret_env_var, "")
        return bool(client_id and client_secret)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for API responses.

        Serializes all metadata fields except callables (auth_url_generator,
        token_exchanger, token_revoker) which are not JSON-serializable.
        Includes the computed `is_configured` status.

        Returns:
            Dictionary with serializable metadata fields.

        Example:
            >>> metadata.to_dict()
            {
                'name': 'gmail',
                'display_name': 'Gmail',
                'description': 'Google Gmail with OAuth2 authentication',
                'icon': 'mdi:google',
                'client_id_env_var': 'GOOGLE_CLIENT_ID',
                'client_secret_env_var': 'GOOGLE_CLIENT_SECRET',
                'scopes': ['https://www.googleapis.com/auth/gmail.readonly'],
                'is_configured': True,
            }
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "client_id_env_var": self.client_id_env_var,
            "client_secret_env_var": self.client_secret_env_var,
            "scopes": list(self.scopes),
            "is_configured": self.is_configured(),
        }


# Private registry for OAuth providers
_OAUTH_PROVIDERS: dict[str, OAuthProviderMetadata] = {}


def register_oauth_provider(metadata: OAuthProviderMetadata) -> OAuthProviderMetadata:
    """Register an OAuth provider in the global registry.

    This function can be used directly or as a decorator factory. When used
    as a decorator on a function that returns OAuthProviderMetadata, it
    auto-registers the provider when the module is imported.

    Args:
        metadata: The OAuthProviderMetadata instance to register.

    Returns:
        The same metadata instance (allows use as decorator).

    Raises:
        ValueError: If a provider with the same name is already registered.

    Example (direct call):
        >>> metadata = OAuthProviderMetadata(name="gmail", ...)
        >>> register_oauth_provider(metadata)

    Example (decorator on function):
        >>> @oauth_provider
        ... def gmail_metadata():
        ...     return OAuthProviderMetadata(name="gmail", ...)
    """
    if metadata.name in _OAUTH_PROVIDERS:
        raise ValueError(
            f"OAuth provider '{metadata.name}' is already registered. "
            f"Use a different name or unregister the existing provider first."
        )

    _OAUTH_PROVIDERS[metadata.name] = metadata
    return metadata


# Type variable for the decorator
F = TypeVar("F", bound=Callable[[], OAuthProviderMetadata])


def oauth_provider(func: F) -> F:
    """Decorator to register an OAuth provider from a factory function.

    Decorates a function that returns OAuthProviderMetadata. When the module
    is imported, the function is called and its result is registered in the
    global OAuth provider registry.

    Args:
        func: A function that returns OAuthProviderMetadata.

    Returns:
        The same function (allows chaining).

    Example:
        >>> @oauth_provider
        ... def gmail_provider():
        ...     return OAuthProviderMetadata(
        ...         name="gmail",
        ...         display_name="Gmail",
        ...         description="Google Gmail with OAuth2 authentication",
        ...         icon="mdi:google",
        ...         client_id_env_var="GOOGLE_CLIENT_ID",
        ...         client_secret_env_var="GOOGLE_CLIENT_SECRET",
        ...         scopes=["https://www.googleapis.com/auth/gmail.readonly"],
        ...         auth_url_generator=generate_gmail_auth_url,
        ...         token_exchanger=exchange_gmail_code,
        ...         token_revoker=revoke_gmail_token,
        ...     )
    """
    metadata = func()
    register_oauth_provider(metadata)
    return func


def get_oauth_provider(name: str) -> OAuthProviderMetadata | None:
    """Get an OAuth provider by name.

    Args:
        name: The provider name (e.g., 'gmail', 'outlook').

    Returns:
        The OAuthProviderMetadata if found, None otherwise.

    Example:
        >>> provider = get_oauth_provider("gmail")
        >>> if provider:
        ...     print(provider.display_name)
        Gmail
    """
    return _OAUTH_PROVIDERS.get(name)


def list_oauth_providers() -> list[OAuthProviderMetadata]:
    """List all registered OAuth providers.

    Returns:
        List of all registered OAuthProviderMetadata instances.

    Example:
        >>> providers = list_oauth_providers()
        >>> for p in providers:
        ...     print(f"{p.name}: {p.display_name}")
        gmail: Gmail
        outlook: Outlook / Microsoft 365
    """
    return list(_OAUTH_PROVIDERS.values())


def list_oauth_provider_metadata() -> list[dict[str, Any]]:
    """List metadata dictionaries for all registered OAuth providers.

    Returns metadata dictionaries for each provider, useful for API endpoints
    to expose available providers and their configuration status.

    Returns:
        List of metadata dictionaries from OAuthProviderMetadata.to_dict().

    Example:
        >>> metadata_list = list_oauth_provider_metadata()
        >>> for m in metadata_list:
        ...     print(f"{m['name']}: configured={m['is_configured']}")
    """
    return [provider.to_dict() for provider in _OAUTH_PROVIDERS.values()]


def is_provider_configured(name: str) -> bool:
    """Check if an OAuth provider is configured.

    Convenience function that checks if a provider exists and has its
    required environment variables set.

    Args:
        name: The provider name (e.g., 'gmail', 'outlook').

    Returns:
        True if the provider exists and is configured, False otherwise.

    Example:
        >>> if is_provider_configured("gmail"):
        ...     # Gmail OAuth is ready to use
        ...     pass
    """
    provider = get_oauth_provider(name)
    return provider.is_configured() if provider else False


def get_configured_providers() -> list[OAuthProviderMetadata]:
    """Get all OAuth providers that are currently configured.

    Returns only providers whose environment variables are set.

    Returns:
        List of configured OAuthProviderMetadata instances.

    Example:
        >>> configured = get_configured_providers()
        >>> print(f"{len(configured)} providers ready to use")
    """
    return [p for p in _OAUTH_PROVIDERS.values() if p.is_configured()]


def unregister_oauth_provider(name: str) -> bool:
    """Unregister an OAuth provider from the registry.

    Primarily useful for testing or dynamic provider management.

    Args:
        name: The provider name to unregister.

    Returns:
        True if the provider was unregistered, False if it wasn't registered.

    Example:
        >>> unregister_oauth_provider("custom_provider")
        True
    """
    if name in _OAUTH_PROVIDERS:
        del _OAUTH_PROVIDERS[name]
        return True
    return False


def clear_oauth_providers() -> None:
    """Clear all registered OAuth providers.

    Warning: This removes ALL providers from the registry. Primarily useful
    for testing. After calling this, you'll need to re-import provider
    modules to re-register built-in providers.

    Example:
        >>> clear_oauth_providers()
        >>> len(list_oauth_providers())
        0
    """
    _OAUTH_PROVIDERS.clear()


__all__ = [
    # Metadata class
    "OAuthProviderMetadata",
    # Type aliases
    "AuthUrlGenerator",
    "TokenExchanger",
    "TokenRevoker",
    # Registration
    "register_oauth_provider",
    "oauth_provider",
    "unregister_oauth_provider",
    "clear_oauth_providers",
    # Lookup
    "get_oauth_provider",
    "list_oauth_providers",
    "list_oauth_provider_metadata",
    "is_provider_configured",
    "get_configured_providers",
]
