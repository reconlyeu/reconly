"""Base fetcher interface.

This module defines the abstract base class for all content fetchers.
Fetchers retrieve content from various sources (RSS feeds, YouTube, websites, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from reconly_core.config_types import ConfigField, ComponentConfigSchema


# Re-export ConfigField for backwards compatibility
__all__ = [
    "ConfigField",
    "FetcherConfigSchema",
    "FetchedItem",
    "BaseFetcher",
    "ValidationResult",
]


@dataclass
class FetcherConfigSchema(ComponentConfigSchema):
    """Configuration schema for a fetcher.

    Inherits fields from ComponentConfigSchema.
    """
    pass


@dataclass
class ValidationResult:
    """Result of source validation.

    This dataclass contains the outcome of validating a source URL and
    configuration before creation or update.

    Attributes:
        valid: Whether the source configuration is valid (no errors)
        errors: List of error messages that prevent source creation
        warnings: List of warning messages (non-blocking issues)
        test_item_count: Number of items fetched during test (if test_fetch=True)
        response_time_ms: Response time in milliseconds for test fetch
        url_type: Detected URL type (e.g., 'video', 'channel', 'feed')

    Example:
        >>> result = ValidationResult(
        ...     valid=True,
        ...     errors=[],
        ...     warnings=["Feed uses deprecated format"],
        ...     test_item_count=10,
        ... )
        >>> if result.valid:
        ...     print("Source is valid!")
    """
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    test_item_count: Optional[int] = None
    response_time_ms: Optional[float] = None
    url_type: Optional[str] = None

    def __post_init__(self) -> None:
        """Ensure valid=False if errors list was pre-populated during construction."""
        if self.errors:
            self.valid = False

    def add_error(self, message: str) -> "ValidationResult":
        """Add an error message and mark as invalid.

        Args:
            message: Error message to add

        Returns:
            Self for method chaining
        """
        self.errors.append(message)
        self.valid = False
        return self

    def add_warning(self, message: str) -> "ValidationResult":
        """Add a warning message (does not affect validity).

        Args:
            message: Warning message to add

        Returns:
            Self for method chaining
        """
        self.warnings.append(message)
        return self

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge another ValidationResult into this one.

        Args:
            other: ValidationResult to merge

        Returns:
            Self for method chaining
        """
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if other.errors:
            self.valid = False
        if other.test_item_count is not None:
            self.test_item_count = other.test_item_count
        if other.response_time_ms is not None:
            self.response_time_ms = other.response_time_ms
        if other.url_type is not None:
            self.url_type = other.url_type
        return self


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

    def validate(
        self,
        url: str,
        config: Optional[Dict[str, Any]] = None,
        test_fetch: bool = False,
        timeout: int = 10,
    ) -> ValidationResult:
        """
        Validate source URL and configuration before creation.

        This method performs validation checks on the source configuration
        without actually creating the source. Subclasses should override
        this method to provide fetcher-specific validation.

        The default implementation validates:
        - URL format (must start with http:// or https://)
        - URL length (must not exceed 2048 characters)
        - Basic URL parsing (must be parseable)

        Subclasses should call super().validate() first, then add their
        own validation logic.

        Args:
            url: Source URL to validate
            config: Additional configuration dictionary (fetcher-specific)
            test_fetch: If True, attempt to fetch content to verify accessibility
            timeout: Timeout in seconds for test fetch operations (default: 10)

        Returns:
            ValidationResult with valid flag, errors, and warnings

        Example:
            >>> fetcher = RSSFetcher()
            >>> result = fetcher.validate("https://example.com/feed.xml", test_fetch=True)
            >>> if result.valid:
            ...     print(f"Valid! Found {result.test_item_count} items")
            ... else:
            ...     print(f"Errors: {result.errors}")
        """
        result = ValidationResult()

        # Validate URL is not empty
        if not url:
            return result.add_error("URL is required")

        # Validate URL is not too long
        max_length = 2048
        if len(url) > max_length:
            return result.add_error(f"URL exceeds maximum length of {max_length} characters")

        # Validate URL format
        if not url.startswith(("http://", "https://")):
            # Allow special URL schemes for specific fetchers (e.g., imap://, agent://)
            if not self._is_valid_scheme(url):
                url_preview = f"{url[:30]}..." if len(url) > 30 else url
                return result.add_error(
                    f"URL must start with http:// or https:// (got: {url_preview})"
                )

        # Validate URL can be parsed
        try:
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https") and not parsed.netloc:
                return result.add_error("URL must include a hostname")
        except Exception as e:
            return result.add_error(f"Invalid URL format: {e}")

        # Warn about HTTP (non-HTTPS) URLs
        if url.startswith("http://"):
            result.add_warning(
                "URL uses HTTP instead of HTTPS. Consider using HTTPS for security."
            )

        return result

    def _is_valid_scheme(self, url: str) -> bool:
        """
        Check if URL has a valid scheme for this fetcher.

        Subclasses can override this to allow fetcher-specific URL schemes
        (e.g., imap://, agent://).

        Args:
            url: URL to check

        Returns:
            True if URL scheme is valid for this fetcher
        """
        # Default: only allow http/https
        return url.startswith(("http://", "https://"))
