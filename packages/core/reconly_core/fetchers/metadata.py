"""Fetcher-specific metadata for content fetchers.

This module defines the FetcherMetadata dataclass that extends ComponentMetadata
with fetcher-specific fields for URL schemes, OAuth support, and fetcher capabilities.

Example:
    >>> from reconly_core.fetchers.metadata import FetcherMetadata
    >>> metadata = FetcherMetadata(
    ...     name="rss",
    ...     display_name="RSS Feed",
    ...     description="Fetch content from RSS/Atom feeds",
    ...     icon="mdi:rss",
    ...     supports_incremental=True,
    ... )
    >>> metadata.to_dict()
    {'name': 'rss', 'display_name': 'RSS Feed', ...}
"""
from dataclasses import dataclass, field
from typing import Any

from reconly_core.metadata import ComponentMetadata


@dataclass
class FetcherMetadata(ComponentMetadata):
    """Metadata for content fetchers.

    Extends ComponentMetadata with fetcher-specific configuration including
    URL scheme support, OAuth capabilities, and feature flags.

    Attributes:
        name: Internal identifier (e.g., 'rss', 'imap', 'youtube').
        display_name: Human-readable name (e.g., 'RSS Feed', 'Email (IMAP)').
        description: Short description of the fetcher.
        icon: Icon identifier for UI (e.g., 'mdi:rss', 'mdi:email').
        url_schemes: List of URL schemes this fetcher handles (e.g., ['http', 'https']).
                     Used for URL validation and auto-detection.
        supports_oauth: Whether the fetcher supports OAuth authentication.
        oauth_providers: List of OAuth provider names (e.g., ['gmail', 'outlook']).
                         Only relevant if supports_oauth is True.
        supports_incremental: Whether the fetcher supports incremental/delta fetching.
                              If True, the fetcher can use 'since' parameter to fetch
                              only new items since last fetch.
        supports_validation: Whether the fetcher supports URL/config validation.
                             If True, the validate() method performs meaningful checks.
        supports_test_fetch: Whether the fetcher supports test fetching during validation.
                             If True, validate() with test_fetch=True will attempt
                             to actually fetch content.
        show_in_settings: Whether the fetcher should appear in the settings UI.
                          Set to False for fetchers with dedicated configuration
                          pages (e.g., Agent Research).

    Example:
        >>> metadata = FetcherMetadata(
        ...     name="imap",
        ...     display_name="Email (IMAP)",
        ...     description="Fetch emails via IMAP protocol",
        ...     icon="mdi:email",
        ...     url_schemes=["imap", "imaps"],
        ...     supports_oauth=True,
        ...     oauth_providers=["gmail", "outlook"],
        ...     supports_incremental=True,
        ... )
    """

    url_schemes: list[str] = field(default_factory=lambda: ['http', 'https'])
    supports_oauth: bool = False
    oauth_providers: list[str] = field(default_factory=list)
    supports_incremental: bool = False
    supports_validation: bool = True
    supports_test_fetch: bool = True
    show_in_settings: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for API responses.

        Extends the base to_dict() to include all fetcher-specific fields.

        Returns:
            Dictionary with all metadata fields serialized.
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "url_schemes": self.url_schemes,
            "supports_oauth": self.supports_oauth,
            "oauth_providers": self.oauth_providers,
            "supports_incremental": self.supports_incremental,
            "supports_validation": self.supports_validation,
            "supports_test_fetch": self.supports_test_fetch,
            "show_in_settings": self.show_in_settings,
        }
