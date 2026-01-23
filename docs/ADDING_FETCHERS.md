# Adding New Content Fetchers

This guide shows you how to add a new content fetcher to Reconly. The self-registering fetcher architecture makes this straightforward.

## Overview

Reconly uses a **fetcher registry pattern** that allows new content sources to be added without modifying core factory code. Contributors can:

1. Create a new fetcher class inheriting from `BaseFetcher`
2. Decorate it with `@register_fetcher('source-type')`
3. Define the `metadata` class variable
4. Implement required abstract methods

The fetcher becomes automatically discoverable and the UI renders it dynamically from metadata.

## Step-by-Step Guide

### 1. Create Your Fetcher Class

Create a new file in `packages/core/reconly_core/fetchers/`:

```python
"""My Custom Source fetcher implementation."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from reconly_core.fetchers.base import BaseFetcher
from reconly_core.fetchers.metadata import FetcherMetadata
from reconly_core.fetchers.registry import register_fetcher


@register_fetcher('my-source')  # <-- Register your fetcher
class MySourceFetcher(BaseFetcher):
    """Fetches content from My Custom Source."""

    # Fetcher metadata (required)
    metadata = FetcherMetadata(
        name='my-source',
        display_name='My Custom Source',
        description='Fetch content from My Custom Source',
        icon='mdi:source-repository',  # Iconify format
        url_schemes=['http', 'https'],
        supports_incremental=True,
        supports_validation=True,
        supports_test_fetch=True,
    )

    def __init__(self, timeout: int = 10):
        """Initialize the fetcher."""
        self.timeout = timeout

    def fetch(
        self,
        url: str,
        since: Optional[datetime] = None,
        max_items: Optional[int] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetch content from the source.

        Args:
            url: Source URL
            since: Only return items published after this datetime
            max_items: Maximum number of items to return

        Returns:
            List of dictionaries with content data
        """
        # Your fetch logic here
        items = self._fetch_from_source(url, since, max_items)

        return items

    def _fetch_from_source(self, url, since, max_items):
        """Implement your source-specific fetching logic."""
        # Example return format
        return [{
            'url': url,
            'title': 'Article Title',
            'content': 'Article content here...',
            'source_type': 'my-source',
            'published': datetime.now().isoformat(),
            'author': 'Author Name',
        }]

    def get_source_type(self) -> str:
        return 'my-source'

    def can_handle(self, url: str) -> bool:
        """Check if this fetcher can handle the URL."""
        return 'my-source.example.com' in url.lower()

    def get_description(self) -> str:
        return 'My Custom Source content fetcher'
```

### 2. Implement Required Abstract Methods

Your fetcher **must** implement these abstract methods:

#### `fetch(url, since, max_items, **kwargs) -> List[Dict[str, Any]]`

Main method that fetches content from the source:

```python
def fetch(
    self,
    url: str,
    since: Optional[datetime] = None,
    max_items: Optional[int] = None,
    **kwargs
) -> List[Dict[str, Any]]:
    """Fetch content from source."""
    items = []

    # Fetch from your source
    raw_items = self._get_items(url)

    for item in raw_items:
        # Filter by date if since is provided
        if since and item.published and item.published <= since:
            continue

        items.append({
            'url': item.url,
            'title': item.title,
            'content': item.content,
            'source_type': self.get_source_type(),
            'published': item.published.isoformat() if item.published else None,
            'author': item.author,
            # Add any source-specific fields
        })

    # Apply max_items limit
    if max_items and len(items) > max_items:
        items = items[:max_items]

    return items
```

**Return format**: Each dictionary should contain at minimum:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `url` | `str` | Yes | Item URL |
| `title` | `str` | Yes | Item title |
| `content` | `str` | Yes | Full content text |
| `source_type` | `str` | Yes | Source type identifier |
| `published` | `str` | No | ISO format datetime string |
| `author` | `str` | No | Author name |

#### `get_source_type() -> str`

Return a unique source type identifier:

```python
def get_source_type(self) -> str:
    return 'my-source'
```

### 3. Define Fetcher Metadata

Every fetcher **must** define a `metadata` class variable of type `FetcherMetadata`. This metadata enables:

- **Dynamic UI rendering** - Frontend displays fetcher names and icons from API
- **Capability-based logic** - Backend uses metadata for feature detection
- **Zero-code extensions** - New fetchers work without frontend changes

```python
from reconly_core.fetchers.metadata import FetcherMetadata

class MySourceFetcher(BaseFetcher):
    metadata = FetcherMetadata(
        name='my-source',             # Must match @register_fetcher name
        display_name='My Custom Source',  # Human-readable name for UI
        description='Fetch content from My Custom Source',
        icon='mdi:source-repository',  # Iconify format

        # URL handling
        url_schemes=['http', 'https'],  # Supported URL schemes

        # OAuth configuration (for authenticated sources)
        supports_oauth=False,           # Whether OAuth is supported
        oauth_providers=[],             # e.g., ['gmail', 'outlook']

        # Capabilities
        supports_incremental=True,      # Supports 'since' parameter
        supports_validation=True,       # Supports validate() method
        supports_test_fetch=True,       # Supports test fetch during validation
    )
```

#### Metadata Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Internal identifier, must match `@register_fetcher` name |
| `display_name` | `str` | Human-readable name for UI display |
| `description` | `str` | Short description for tooltips/help |
| `icon` | `str \| None` | Iconify icon identifier (e.g., `mdi:rss`) |
| `url_schemes` | `list[str]` | Supported URL schemes (default: `['http', 'https']`) |
| `supports_oauth` | `bool` | Whether OAuth authentication is supported |
| `oauth_providers` | `list[str]` | OAuth provider names (e.g., `['gmail']`) |
| `supports_incremental` | `bool` | Whether delta/incremental fetching is supported |
| `supports_validation` | `bool` | Whether URL validation is supported |
| `supports_test_fetch` | `bool` | Whether test fetching during validation is supported |

#### Using Metadata for Capability-Based Logic

Replace type checks with capability queries:

```python
# Before (hardcoded)
if source.source_type == 'imap':
    handle_oauth_flow()

# After (metadata-driven)
fetcher = get_fetcher(source.source_type)
if fetcher.metadata.supports_oauth:
    handle_oauth_flow()
```

For more details on the metadata system, see [Component Metadata Architecture](architecture/component-metadata.md).

### 4. Optional: Override can_handle()

Enable auto-detection of your source type from URLs:

```python
def can_handle(self, url: str) -> bool:
    """Check if this fetcher can handle the given URL."""
    url_lower = url.lower()

    # Define URL patterns your fetcher handles
    patterns = [
        'my-source.example.com',
        '/my-source/',
    ]

    return any(pattern in url_lower for pattern in patterns)
```

This enables `detect_fetcher(url)` to automatically select your fetcher.

### 4. Optional: Override get_description()

Provide a human-readable description:

```python
def get_description(self) -> str:
    return 'My Custom Source - fetches articles and posts'
```

### 5. Create Tests

Create `tests/core/fetchers/test_my_source.py`:

```python
"""Tests for My Source fetcher."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from reconly_core.fetchers import get_fetcher, list_fetchers


class TestMySourceFetcher:
    """Tests for MySourceFetcher."""

    def test_registered(self):
        """Test that fetcher is registered."""
        assert 'my-source' in list_fetchers()

    def test_get_source_type(self):
        """Test get_source_type returns correct value."""
        fetcher = get_fetcher('my-source')
        assert fetcher.get_source_type() == 'my-source'

    def test_can_handle_matching_url(self):
        """Test can_handle returns True for matching URLs."""
        fetcher = get_fetcher('my-source')
        assert fetcher.can_handle('https://my-source.example.com/article')

    def test_can_handle_non_matching_url(self):
        """Test can_handle returns False for non-matching URLs."""
        fetcher = get_fetcher('my-source')
        assert not fetcher.can_handle('https://other.example.com/page')

    @patch('reconly_core.fetchers.my_source.requests.get')
    def test_fetch_success(self, mock_get):
        """Test successful fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'items': [
                {'title': 'Test', 'content': 'Content', 'url': 'http://...'}
            ]
        }
        mock_get.return_value = mock_response

        fetcher = get_fetcher('my-source')
        items = fetcher.fetch('https://my-source.example.com/feed')

        assert len(items) >= 0
        # Add more specific assertions

    def test_fetch_respects_max_items(self):
        """Test that fetch respects max_items parameter."""
        # Your test implementation
        pass

    def test_fetch_filters_by_since(self):
        """Test that fetch filters items by since datetime."""
        # Your test implementation
        pass
```

### 6. Register Your Fetcher

Your fetcher is **automatically registered** when the module is imported thanks to the `@register_fetcher` decorator.

To ensure it's loaded, import it in `factory.py`:

```python
# In factory.py
from reconly_core.fetchers import my_source
```

### 7. Use Your Fetcher

```python
from reconly_core.fetchers import get_fetcher, detect_fetcher

# Get fetcher by source type
fetcher = get_fetcher('my-source')
items = fetcher.fetch(url, since=since, max_items=10)

# Auto-detect fetcher from URL
fetcher = detect_fetcher('https://my-source.example.com/feed')
if fetcher:
    items = fetcher.fetch(url)
```

## Working with Feed Service

Once registered, your fetcher works automatically with `feed_service.py`:

```python
# In database, create a Source with type='my-source'
source = Source(
    name='My Source Feed',
    url='https://my-source.example.com/feed',
    type='my-source',  # <-- Your source type
    enabled=True
)
```

The feed service will automatically use your fetcher when processing this source.

## FetchedItem Dataclass (Optional)

For structured typing, you can use the `FetchedItem` dataclass:

```python
from reconly_core.fetchers.base import FetchedItem

item = FetchedItem(
    url='https://example.com/article',
    title='Article Title',
    content='Article content...',
    published=datetime.now(),
    author='Author Name',
    source_type='my-source',
    metadata={'custom_field': 'value'}
)

# Convert to dict for compatibility
item_dict = item.to_dict()
```

## Handling Pagination

For sources with pagination:

```python
def fetch(self, url, since=None, max_items=None, **kwargs):
    items = []
    page = 1

    while True:
        page_items = self._fetch_page(url, page)
        if not page_items:
            break

        for item in page_items:
            # Filter by date
            if since and item.get('published'):
                published_dt = datetime.fromisoformat(item['published'])
                if published_dt <= since:
                    continue

            items.append(item)

            # Stop if we have enough
            if max_items and len(items) >= max_items:
                return items[:max_items]

        page += 1

    return items
```

## Built-in Fetchers

Look at existing fetchers for examples:

- `rss.py` - RSS/Atom feed fetcher with date filtering
- `youtube.py` - YouTube video/channel transcript fetcher
- `website.py` - Generic website content extractor

## Fetcher Architecture

```
┌─────────────────────────────────────────────────┐
│ BaseFetcher (Abstract)                          │
│ - fetch()                                       │
│ - get_source_type()                             │
│ - can_handle() [optional]                       │
│ - get_description() [optional]                  │
└─────────────────────────────────────────────────┘
                     ▲
                     │ inherits
        ┌────────────┴────────────┐
        │                         │
┌───────────────┐         ┌───────────────┐
│ @register_fetcher('rss')   @register_fetcher('youtube')
│ RSSFetcher    │         │ YouTubeFetcher│
└───────────────┘         └───────────────┘
        │                         │
        └────────────┬────────────┘
                     │ registered in
           ┌─────────────────────┐
           │ _FETCHER_REGISTRY   │
           │ {                   │
           │   'rss': RSSClass   │
           │   'youtube': YTClass│
           │ }                   │
           └─────────────────────┘
                     │
                     │ used by
              ┌──────────────┐
              │ get_fetcher  │
              │ detect_fetcher │
              └──────────────┘
```

## Configuration Schema (Settings Integration)

Fetchers can define a configuration schema to enable settings management through the UI. This allows users to configure API keys, credentials, and other fetcher-specific options.

### Adding Config Schema

Override the `get_config_schema()` method to declare your fetcher's configuration requirements:

```python
from reconly_core.fetchers.base import BaseFetcher, FetcherConfigSchema
from reconly_core.fetchers.registry import register_fetcher
from reconly_core.config_types import ConfigField

@register_fetcher('reddit')
class RedditFetcher(BaseFetcher):
    """Fetch content from Reddit."""

    def get_config_schema(self) -> FetcherConfigSchema:
        return FetcherConfigSchema(
            fields=[
                ConfigField(
                    key="client_id",
                    type="string",
                    label="Reddit Client ID",
                    description="Your Reddit API client ID",
                    required=True,
                    env_var="REDDIT_CLIENT_ID",
                    editable=False,  # Credential - env only
                    secret=True
                ),
                ConfigField(
                    key="client_secret",
                    type="string",
                    label="Reddit Client Secret",
                    description="Your Reddit API client secret",
                    required=True,
                    env_var="REDDIT_CLIENT_SECRET",
                    editable=False,
                    secret=True
                ),
                ConfigField(
                    key="user_agent",
                    type="string",
                    label="User Agent",
                    description="User agent string for API requests",
                    default="Reconly/1.0",
                    required=False
                ),
            ],
            supports_incremental_fetch=True
        )
```

### ConfigField Attributes

| Attribute | Description |
|-----------|-------------|
| `key` | Setting key (e.g., "api_key", "timeout") |
| `type` | Field type: "string", "boolean", "integer", or "path" |
| `label` | Human-readable label for UI |
| `description` | Help text describing the field |
| `default` | Default value if not configured |
| `required` | Whether field is required for fetcher to function |
| `placeholder` | Input placeholder text for UI |
| `env_var` | Environment variable name (e.g., "YOUTUBE_API_KEY") |
| `editable` | Whether field can be edited via UI (False = env-only for secrets) |
| `secret` | Whether field contains sensitive data (masked in responses) |

### Settings Auto-Registration

When you use the `@register_fetcher` decorator, the fetcher's settings are automatically registered with the pattern:

```
fetch.{name}.{field}
```

**Examples:**
- `fetch.youtube.api_key` - YouTube Data API key
- `fetch.reddit.client_id` - Reddit client ID
- `fetch.reddit.user_agent` - Reddit user agent string

### Accessing Configuration

Settings configured via the UI are available through the settings service. Access them in your fetch method:

```python
from reconly_core.services.settings_service import SettingsService

def fetch(self, url, since=None, max_items=None, **kwargs):
    settings = SettingsService()
    api_key = settings.get('fetch.youtube.api_key')

    if not api_key:
        raise ValueError("YouTube API key not configured")

    # Use api_key for API calls
    ...
```

### Best Practices for Configuration

1. **Use `secret=True`** for API keys, tokens, and passwords
2. **Set `editable=False`** for credentials to enforce environment-only configuration
3. **Provide `env_var`** names for all sensitive fields
4. **Mark fields as `required=True`** if the fetcher cannot function without them
5. **Provide sensible defaults** for optional configuration

## Best Practices

1. **Always include `source_type`** in returned dictionaries
2. **Handle `since` filtering** to avoid re-processing old items
3. **Respect `max_items`** to limit API calls and processing
4. **Return empty list** instead of raising for "no items found"
5. **Use `can_handle()`** for URL-based auto-detection
6. **Handle network errors gracefully** with informative messages
7. **Parse dates consistently** - use ISO format for `published` field

## Testing Checklist

Before submitting your fetcher:

- [ ] All abstract methods implemented
- [ ] Tests for basic fetch operation
- [ ] Tests for `since` date filtering
- [ ] Tests for `max_items` limiting
- [ ] Tests for `can_handle()` if implemented
- [ ] `pytest tests/core/fetchers/test_my_source.py` passes
- [ ] Returns correct `source_type` in items

## Packaging as an Extension

Want to distribute your fetcher as an installable package? See the [Extension Development Guide](./EXTENSION_DEVELOPMENT.md) for full details. Here's a quick overview:

### 1. Create Package Structure

```
reconly-ext-reddit/
├── pyproject.toml
├── README.md
├── src/
│   └── reconly_ext_reddit/
│       ├── __init__.py
│       └── fetcher.py
└── tests/
```

### 2. Add Extension Metadata

Add these class attributes to your fetcher:

```python
class RedditFetcher(BaseFetcher):
    # Extension metadata
    __extension_name__ = "Reddit Fetcher"
    __extension_version__ = "1.0.0"
    __extension_author__ = "Your Name"
    __extension_min_reconly__ = "0.5.0"
    __extension_description__ = "Fetch posts from Reddit subreddits"
    __extension_homepage__ = "https://github.com/you/reconly-ext-reddit"

    # ... rest of implementation
```

### 3. Configure Entry Points

In `pyproject.toml`:

```toml
[project]
name = "reconly-ext-reddit"
version = "1.0.0"
dependencies = ["reconly-core>=0.5.0"]

[project.entry-points."reconly.fetchers"]
reddit = "reconly_ext_reddit:RedditFetcher"
```

### 4. Install and Test

```bash
pip install -e .
# Restart Reconly - extension appears in Settings > Extensions
```

---

## Questions?

- Check existing fetchers in `packages/core/reconly_core/fetchers/`
- Review test examples in `tests/core/fetchers/`
- See [Extension Development Guide](./EXTENSION_DEVELOPMENT.md) for packaging details
- Open an issue on GitHub if stuck
