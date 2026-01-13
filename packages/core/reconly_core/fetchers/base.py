"""Base fetcher interface.

This module defines the abstract base class for all content fetchers.
Fetchers retrieve content from various sources (RSS feeds, YouTube, websites, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from reconly_core.config_types import ConfigField, ComponentConfigSchema


# Re-export ConfigField for backwards compatibility
__all__ = ["ConfigField", "FetcherConfigSchema", "FetchedItem", "BaseFetcher"]


@dataclass
class FetcherConfigSchema(ComponentConfigSchema):
    """Configuration schema for a fetcher.

    Inherits fields from ComponentConfigSchema.
    """
    pass


@dataclass
class FetchedItem:
    """A single fetched content item.

    Attributes:
        url: Source URL for the item
        title: Item title
        content: Full content text
        published: Publication datetime (optional)
        author: Author name (optional)
        source_type: Type of source (e.g., 'rss', 'youtube', 'website')
        metadata: Additional format-specific metadata
    """
    url: str
    title: str
    content: str
    published: Optional[datetime] = None
    author: Optional[str] = None
    source_type: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format compatible with existing summarizers."""
        result = {
            'url': self.url,
            'title': self.title,
            'content': self.content,
            'source_type': self.source_type,
        }
        if self.published:
            result['published'] = self.published.isoformat()
        if self.author:
            result['author'] = self.author
        if self.metadata:
            result.update(self.metadata)
        return result


class BaseFetcher(ABC):
    """Abstract base class for content fetchers.

    Subclasses must implement all abstract methods to provide source-specific
    fetching functionality.

    Example:
        >>> @register_fetcher('rss')
        >>> class RSSFetcher(BaseFetcher):
        >>>     def fetch(self, url, since=None, max_items=None):
        >>>         # Fetch logic here
        >>>         return [{'url': ..., 'title': ..., 'content': ...}]
    """

    @abstractmethod
    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch content from a source.

        Args:
            url: Source URL
            since: Only return items published after this datetime
            max_items: Maximum number of items to return

        Returns:
            List of dictionaries, each containing at minimum:
            - url: Item URL
            - title: Item title
            - content: Item content
            - source_type: Source type identifier
        """
        pass

    @abstractmethod
    def get_source_type(self) -> str:
        """
        Get the source type identifier.

        Returns:
            Source type (e.g., 'rss', 'youtube', 'website')
        """
        pass

    def can_handle(self, url: str) -> bool:
        """
        Check if this fetcher can handle the given URL.

        Default implementation returns False. Override for URL-based auto-detection.

        Args:
            url: URL to check

        Returns:
            True if this fetcher can handle the URL
        """
        return False

    def get_description(self) -> str:
        """
        Get a human-readable description of this fetcher.

        Returns:
            Description string
        """
        return f"{self.get_source_type().upper()} fetcher"

    def get_config_schema(self) -> FetcherConfigSchema:
        """
        Get the configuration schema for this fetcher.

        Override this method in subclasses to declare configurable settings.
        The default implementation returns an empty schema with no fields.

        Returns:
            FetcherConfigSchema with field definitions
        """
        return FetcherConfigSchema(fields=[])
